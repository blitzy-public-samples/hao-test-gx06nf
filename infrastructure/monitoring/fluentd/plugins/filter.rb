# frozen_string_literal: true

# fluentd v1.14.0
require 'fluent/filter'
# prometheus-client v2.1.0
require 'prometheus/client'

# Custom filter for API service logs implementing request/response metrics extraction
# and log enrichment with enhanced service identification and detailed performance tracking
class Fluent::APILogFilter < Fluent::Filter
  Fluent::Plugin.register_filter('api_log')

  # Configuration parameters
  config_param :metrics_prefix, :string
  config_param :service_name, :string

  def initialize
    super
    @registry = Prometheus::Client.registry

    # Initialize request counter with method, path and status labels
    @request_counter = Prometheus::Client::Counter.new(
      :"#{@metrics_prefix}_api_requests_total",
      docstring: 'Total number of API requests',
      labels: [:method, :path, :status]
    )

    # Initialize response time histogram with custom buckets
    @response_histogram = Prometheus::Client::Histogram.new(
      :"#{@metrics_prefix}_api_response_seconds",
      docstring: 'API response time in seconds',
      labels: [:method, :path],
      buckets: [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    )

    # Register metrics
    @registry.register(@request_counter)
    @registry.register(@response_histogram)
  end

  def configure(conf)
    super(conf)
    raise Fluent::ConfigError, "metrics_prefix is required" unless @metrics_prefix
    raise Fluent::ConfigError, "service_name is required" unless @service_name
  end

  def filter(_tag, _time, record)
    # Extract request details
    method = record['method'] || 'UNKNOWN'
    path = record['path'] || 'UNKNOWN'
    status = record['status'] || 500
    response_time = record['response_time'].to_f

    # Update metrics
    @request_counter.increment(labels: { method: method, path: path, status: status })
    @response_histogram.observe(response_time, labels: { method: method, path: path })

    # Enrich log record
    record['service'] = @service_name
    record['environment'] = ENV['ENVIRONMENT'] || 'production'
    record['request_id'] = record['request_id'] || SecureRandom.uuid
    
    # Add performance impact classification
    record['performance_impact'] = case response_time
      when 0..0.1 then 'minimal'
      when 0.1..0.5 then 'low'
      when 0.5..2.0 then 'medium'
      when 2.0..5.0 then 'high'
      else 'critical'
    end

    record
  end
end

# Custom filter for PostgreSQL database logs with comprehensive query performance tracking
class Fluent::DatabaseLogFilter < Fluent::Filter
  Fluent::Plugin.register_filter('db_log')

  # Configuration parameters
  config_param :metrics_prefix, :string

  def initialize
    super
    @registry = Prometheus::Client.registry

    # Initialize query time histogram
    @query_histogram = Prometheus::Client::Histogram.new(
      :"#{@metrics_prefix}_db_query_seconds",
      docstring: 'Database query execution time in seconds',
      labels: [:operation, :table],
      buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
    )

    @registry.register(@query_histogram)
  end

  def filter(_tag, _time, record)
    # Extract and classify query details
    query_time = record['duration'].to_f
    query = record['query'] || ''
    
    # Determine operation type
    operation = case query.strip.upcase
      when /^SELECT/ then 'SELECT'
      when /^INSERT/ then 'INSERT'
      when /^UPDATE/ then 'UPDATE'
      when /^DELETE/ then 'DELETE'
      else 'OTHER'
    end

    # Extract table name (simplified)
    table = query.match(/FROM\s+(\w+)/i)&.[](1) || 'unknown'

    # Update metrics
    @query_histogram.observe(query_time, labels: { operation: operation, table: table })

    # Enrich log record
    record['query_type'] = operation
    record['table'] = table
    record['performance_impact'] = case query_time
      when 0..0.001 then 'minimal'
      when 0.001..0.01 then 'low'
      when 0.01..0.1 then 'medium'
      when 0.1..1.0 then 'high'
      else 'critical'
    end

    record
  end
end

# Custom filter for Redis cache logs with detailed operation tracking
class Fluent::CacheLogFilter < Fluent::Filter
  Fluent::Plugin.register_filter('cache_log')

  # Configuration parameters
  config_param :metrics_prefix, :string

  def initialize
    super
    @registry = Prometheus::Client.registry

    # Initialize operation counter
    @operation_counter = Prometheus::Client::Counter.new(
      :"#{@metrics_prefix}_cache_operations_total",
      docstring: 'Total number of cache operations',
      labels: [:operation, :status]
    )

    @registry.register(@operation_counter)
  end

  def filter(_tag, _time, record)
    # Extract operation details
    operation = record['command'] || 'unknown'
    status = record['status'] || 'error'
    latency = record['latency'].to_f

    # Update metrics
    @operation_counter.increment(labels: { operation: operation, status: status })

    # Enrich log record
    record['operation_type'] = operation
    record['success'] = status == 'success'
    record['performance_impact'] = case latency
      when 0..0.001 then 'minimal'
      when 0.001..0.005 then 'low'
      when 0.005..0.01 then 'medium'
      when 0.01..0.1 then 'high'
      else 'critical'
    end

    # Add memory usage impact if available
    if record['used_memory']
      record['memory_impact'] = case record['used_memory'].to_i
        when 0..1024 then 'minimal'
        when 1024..10240 then 'low'
        when 10240..102400 then 'medium'
        else 'high'
      end
    end

    record
  end
end