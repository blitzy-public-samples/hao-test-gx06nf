require 'fluent/parser'
require 'json'
require 'time'

# @version fluentd 1.14.0
# Custom parser plugin for API service logs with enhanced performance metrics
module Fluent::Plugin
  class APILogParser < Parser
    Fluent::Plugin.register_parser('api_log')

    config_param :time_format, :string, default: '%Y-%m-%dT%H:%M:%S.%NZ'
    config_param :keep_time_key, :bool, default: false
    config_param :cache_size, :integer, default: 1000
    config_param :detailed_metrics, :bool, default: true

    def initialize
      super
      @pattern_cache = {}
      @cache_size = 1000
      @detailed_metrics = true
      @error_count = 0
      @request_count = 0
    end

    def configure(conf)
      super(conf)
      @time_format = conf['time_format'] || '%Y-%m-%dT%H:%M:%S.%NZ'
      @cache_size = conf['cache_size']&.to_i || 1000
      @detailed_metrics = conf['detailed_metrics']&.downcase == 'true'
      @pattern_cache.clear
    end

    def parse(text)
      begin
        record = JSON.parse(text)
        time = parse_time(record.delete('timestamp'))
        
        # Enhance record with request metrics
        if record['request']
          record['request'] = enhance_request_metrics(record['request'])
        end

        # Add performance tracking
        record['performance_metrics'] = extract_performance_metrics(record) if @detailed_metrics
        
        yield time, record
      rescue JSON::ParserError => e
        @error_count += 1
        yield nil, {'error' => 'JSON parse error', 'raw_message' => text, 'error_detail' => e.message}
      rescue => e
        @error_count += 1
        yield nil, {'error' => 'Parse error', 'raw_message' => text, 'error_detail' => e.message}
      end
    end

    private

    def parse_time(timestamp)
      return Time.now unless timestamp
      Time.strptime(timestamp, @time_format)
    rescue
      Time.now
    end

    def enhance_request_metrics(request)
      @request_count += 1
      path = normalize_path(request['path'])
      
      {
        'method' => request['method']&.upcase,
        'normalized_path' => path,
        'path_pattern' => get_cached_pattern(path),
        'headers' => sanitize_headers(request['headers']),
        'processing_time' => request['processing_time'],
        'request_id' => request['request_id']
      }
    end

    def normalize_path(path)
      return '' unless path
      path.gsub(/\/\d+/, '/:id')
    end

    def get_cached_pattern(path)
      return @pattern_cache[path] if @pattern_cache.key?(path)
      
      if @pattern_cache.size >= @cache_size
        @pattern_cache.shift
      end
      
      pattern = path.split('/').map { |segment| 
        segment.match(/^\d+$/) ? ':id' : segment 
      }.join('/')
      
      @pattern_cache[path] = pattern
      pattern
    end

    def sanitize_headers(headers)
      return {} unless headers.is_a?(Hash)
      
      headers.each_with_object({}) do |(key, value), sanitized|
        # Remove sensitive information
        next if ['authorization', 'cookie'].include?(key.downcase)
        sanitized[key] = value
      end
    end

    def extract_performance_metrics(record)
      {
        'response_time' => record['response_time'],
        'db_query_count' => record['db_queries']&.size || 0,
        'cache_hits' => record['cache_stats']&.fetch('hits', 0),
        'cache_misses' => record['cache_stats']&.fetch('misses', 0),
        'error_count' => @error_count,
        'request_count' => @request_count
      }
    end
  end

  # Advanced parser for PostgreSQL database logs
  class DatabaseLogParser < Parser
    Fluent::Plugin.register_parser('db_log')

    config_param :time_format, :string, default: '%Y-%m-%d %H:%M:%S.%N %Z'
    config_param :track_transactions, :bool, default: true
    config_param :slow_query_threshold, :integer, default: 1000 # milliseconds

    def initialize
      super
      @transaction_cache = {}
      @slow_query_count = 0
      @total_queries = 0
    end

    def parse(text)
      begin
        time, record = extract_db_log_components(text)
        record = enhance_db_metrics(record)
        
        yield time, record
      rescue => e
        yield nil, {'error' => 'Parse error', 'raw_message' => text, 'error_detail' => e.message}
      end
    end

    private

    def extract_db_log_components(text)
      # PostgreSQL log format: timestamp [process_id] LOG:  message
      if text =~ /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \w+) \[(\d+)\] (\w+):\s+(.+)/
        time = Time.strptime($1, @time_format)
        record = {
          'process_id' => $2,
          'log_level' => $3,
          'message' => $4,
          'component' => 'postgresql'
        }
        [time, record]
      else
        [Time.now, {'message' => text, 'parse_error' => true}]
      end
    end

    def enhance_db_metrics(record)
      @total_queries += 1
      
      # Extract query execution time if available
      if record['message'] =~ /duration: (\d+\.\d+) ms/
        duration = $1.to_f
        record['query_time'] = duration
        
        if duration >= @slow_query_threshold
          @slow_query_count += 1
          record['slow_query'] = true
        end
      end

      # Track transactions if enabled
      if @track_transactions && record['message'] =~ /transaction/i
        track_transaction(record)
      end

      record['metrics'] = {
        'total_queries' => @total_queries,
        'slow_queries' => @slow_query_count
      }

      record
    end

    def track_transaction(record)
      if record['message'] =~ /BEGIN/i
        @transaction_cache[record['process_id']] = Time.now
      elsif record['message'] =~ /COMMIT|ROLLBACK/i
        if start_time = @transaction_cache.delete(record['process_id'])
          record['transaction_duration'] = ((Time.now - start_time) * 1000).to_i
        end
      end
    end
  end

  # Specialized parser for Redis cache logs
  class CacheLogParser < Parser
    Fluent::Plugin.register_parser('cache_log')

    config_param :time_format, :string, default: '%d %b %H:%M:%S.%N'
    config_param :track_memory, :bool, default: true
    config_param :operation_threshold, :integer, default: 100 # milliseconds

    def initialize
      super
      @operation_stats = {
        'get' => 0,
        'set' => 0,
        'del' => 0,
        'slow_operations' => 0
      }
    end

    def parse(text)
      begin
        time, record = extract_cache_log_components(text)
        record = enhance_cache_metrics(record)
        
        yield time, record
      rescue => e
        yield nil, {'error' => 'Parse error', 'raw_message' => text, 'error_detail' => e.message}
      end
    end

    private

    def extract_cache_log_components(text)
      # Redis log format: timestamp pid:role message
      if text =~ /^(\d{2} \w{3} \d{2}:\d{2}:\d{2}\.\d+) (\d+):(\w+) (.+)/
        time = Time.strptime($1, @time_format)
        record = {
          'process_id' => $2,
          'role' => $3,
          'message' => $4,
          'component' => 'redis'
        }
        [time, record]
      else
        [Time.now, {'message' => text, 'parse_error' => true}]
      end
    end

    def enhance_cache_metrics(record)
      # Track operation types
      case record['message']
      when /^get /i
        @operation_stats['get'] += 1
        record['operation'] = 'get'
      when /^set /i
        @operation_stats['set'] += 1
        record['operation'] = 'set'
      when /^del /i
        @operation_stats['del'] += 1
        record['operation'] = 'del'
      end

      # Extract operation timing if available
      if record['message'] =~ /\((\d+\.\d+) ms\)/
        duration = $1.to_f
        record['operation_time'] = duration
        
        if duration >= @operation_threshold
          @operation_stats['slow_operations'] += 1
          record['slow_operation'] = true
        end
      end

      # Track memory usage if enabled
      if @track_memory && record['message'] =~ /used_memory:(\d+)/
        record['memory_usage'] = $1.to_i
      end

      record['metrics'] = @operation_stats.dup
      record
    end
  end
end