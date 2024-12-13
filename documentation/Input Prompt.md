I would like you to help me generating the backend for this web application. Your tech stack is python, flask, postgres sql, google cloud user store. You need to deliver a set of REST api as well as their implementations in python.

Here are the definitions of domain entities:

\* A user can login and logout the system backed by google cloud user store

\* A specification is a text string with a unique numeric ID

\* each specification can have 0 or more but less than 10 bullet items. The items are ordered and each of them can be identifiedy by a ID unique in its parent specification.

\* A project is a list of specifications with a text title. A project is owned by one user. Only that user can write and update data within a project.

\* A specification can only belong to one project.

0\. design the database schema for this application

1\. give me a REST API to return a ordered list of top-level specfications stored in the database.

2\. give me a REST API to delete a specification by an unique ID. If there exists second-level items, throw error.

3\. give me a REST API to return all second-level items in a specification by a unique ID

4\. give me a REST API that returns all projects created by a user