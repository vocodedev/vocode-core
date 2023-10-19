# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=too-many-lines

from enum import Enum


class SpanAttributes:
    AWS_LAMBDA_INVOKED_ARN = "aws.lambda.invoked_arn"
    """
    The full invoked ARN as provided on the `Context` passed to the function (`Lambda-Runtime-Invoked-Function-Arn` header on the `/runtime/invocation/next` applicable).
    Note: This may be different from `faas.id` if an alias is involved.
    """

    CLOUDEVENTS_EVENT_ID = "cloudevents.event_id"
    """
    The [event_id](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md#id) uniquely identifies the event.
    """

    CLOUDEVENTS_EVENT_SOURCE = "cloudevents.event_source"
    """
    The [source](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md#source-1) identifies the context in which an event happened.
    """

    CLOUDEVENTS_EVENT_SPEC_VERSION = "cloudevents.event_spec_version"
    """
    The [version of the CloudEvents specification](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md#specversion) which the event uses.
    """

    CLOUDEVENTS_EVENT_TYPE = "cloudevents.event_type"
    """
    The [event_type](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md#type) contains a value describing the type of event related to the originating occurrence.
    """

    CLOUDEVENTS_EVENT_SUBJECT = "cloudevents.event_subject"
    """
    The [subject](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md#subject) of the event in the context of the event producer (identified by source).
    """

    OPENTRACING_REF_TYPE = "opentracing.ref_type"
    """
    Parent-child Reference type.
    Note: The causal relationship between a child Span and a parent Span.
    """

    DB_SYSTEM = "db.system"
    """
    An identifier for the database management system (DBMS) product being used. See below for a list of well-known identifiers.
    """

    DB_CONNECTION_STRING = "db.connection_string"
    """
    The connection string used to connect to the database. It is recommended to remove embedded credentials.
    """

    DB_USER = "db.user"
    """
    Username for accessing the database.
    """

    DB_JDBC_DRIVER_CLASSNAME = "db.jdbc.driver_classname"
    """
    The fully-qualified class name of the [Java Database Connectivity (JDBC)](https://docs.oracle.com/javase/8/docs/technotes/guides/jdbc/) driver used to connect.
    """

    DB_NAME = "db.name"
    """
    This attribute is used to report the name of the database being accessed. For commands that switch the database, this should be set to the target database (even if the command fails).
    Note: In some SQL databases, the database name to be used is called "schema name". In case there are multiple layers that could be considered for database name (e.g. Oracle instance name and schema name), the database name to be used is the more specific layer (e.g. Oracle schema name).
    """

    DB_STATEMENT = "db.statement"
    """
    The database statement being executed.
    Note: The value may be sanitized to exclude sensitive information.
    """

    DB_OPERATION = "db.operation"
    """
    The name of the operation being executed, e.g. the [MongoDB command name](https://docs.mongodb.com/manual/reference/command/#database-operations) such as `findAndModify`, or the SQL keyword.
    Note: When setting this to an SQL keyword, it is not recommended to attempt any client-side parsing of `db.statement` just to get this property, but it should be set if the operation name is provided by the library being instrumented. If the SQL statement has an ambiguous operation, or performs more than one operation, this value may be omitted.
    """

    NET_PEER_NAME = "net.peer.name"
    """
    Remote hostname or similar, see note below.
    Note: `net.peer.name` SHOULD NOT be set if capturing it would require an extra DNS lookup.
    """

    NET_PEER_IP = "net.peer.ip"
    """
    Remote address of the peer (dotted decimal for IPv4 or [RFC5952](https://tools.ietf.org/html/rfc5952) for IPv6).
    """

    NET_PEER_PORT = "net.peer.port"
    """
    Remote port number.
    """

    NET_TRANSPORT = "net.transport"
    """
    Transport protocol used. See note below.
    """

    DB_MSSQL_INSTANCE_NAME = "db.mssql.instance_name"
    """
    The Microsoft SQL Server [instance name](https://docs.microsoft.com/en-us/sql/connect/jdbc/building-the-connection-url?view=sql-server-ver15) connecting to. This name is used to determine the port of a named instance.
    Note: If setting a `db.mssql.instance_name`, `net.peer.port` is no longer required (but still recommended if non-standard).
    """

    DB_CASSANDRA_PAGE_SIZE = "db.cassandra.page_size"
    """
    The fetch size used for paging, i.e. how many rows will be returned at once.
    """

    DB_CASSANDRA_CONSISTENCY_LEVEL = "db.cassandra.consistency_level"
    """
    The consistency level of the query. Based on consistency values from [CQL](https://docs.datastax.com/en/cassandra-oss/3.0/cassandra/dml/dmlConfigConsistency.html).
    """

    DB_CASSANDRA_TABLE = "db.cassandra.table"
    """
    The name of the primary table that the operation is acting upon, including the keyspace name (if applicable).
    Note: This mirrors the db.sql.table attribute but references cassandra rather than sql. It is not recommended to attempt any client-side parsing of `db.statement` just to get this property, but it should be set if it is provided by the library being instrumented. If the operation is acting upon an anonymous table, or more than one table, this value MUST NOT be set.
    """

    DB_CASSANDRA_IDEMPOTENCE = "db.cassandra.idempotence"
    """
    Whether or not the query is idempotent.
    """

    DB_CASSANDRA_SPECULATIVE_EXECUTION_COUNT = (
        "db.cassandra.speculative_execution_count"
    )
    """
    The number of times a query was speculatively executed. Not set or `0` if the query was not executed speculatively.
    """

    DB_CASSANDRA_COORDINATOR_ID = "db.cassandra.coordinator.id"
    """
    The ID of the coordinating node for a query.
    """

    DB_CASSANDRA_COORDINATOR_DC = "db.cassandra.coordinator.dc"
    """
    The data center of the coordinating node for a query.
    """

    DB_REDIS_DATABASE_INDEX = "db.redis.database_index"
    """
    The index of the database being accessed as used in the [`SELECT` command](https://redis.io/commands/select), provided as an integer. To be used instead of the generic `db.name` attribute.
    """

    DB_MONGODB_COLLECTION = "db.mongodb.collection"
    """
    The collection being accessed within the database stated in `db.name`.
    """

    DB_SQL_TABLE = "db.sql.table"
    """
    The name of the primary table that the operation is acting upon, including the database name (if applicable).
    Note: It is not recommended to attempt any client-side parsing of `db.statement` just to get this property, but it should be set if it is provided by the library being instrumented. If the operation is acting upon an anonymous table, or more than one table, this value MUST NOT be set.
    """

    EXCEPTION_TYPE = "exception.type"
    """
    The type of the exception (its fully-qualified class name, if applicable). The dynamic type of the exception should be preferred over the static type in languages that support it.
    """

    EXCEPTION_MESSAGE = "exception.message"
    """
    The exception message.
    """

    EXCEPTION_STACKTRACE = "exception.stacktrace"
    """
    A stacktrace as a string in the natural representation for the language runtime. The representation is to be determined and documented by each language SIG.
    """

    EXCEPTION_ESCAPED = "exception.escaped"
    """
    SHOULD be set to true if the exception event is recorded at a point where it is known that the exception is escaping the scope of the span.
    Note: An exception is considered to have escaped (or left) the scope of a span,
if that span is ended while the exception is still logically "in flight".
This may be actually "in flight" in some languages (e.g. if the exception
is passed to a Context manager's `__exit__` method in Python) but will
usually be caught at the point of recording the exception in most languages.

It is usually not possible to determine at the point where an exception is thrown
whether it will escape the scope of a span.
However, it is trivial to know that an exception
will escape, if one checks for an active exception just before ending the span,
as done in the [example above](#recording-an-exception).

It follows that an exception may still escape the scope of the span
even if the `exception.escaped` attribute was not set or set to false,
since the event might have been recorded at a time where it was not
clear whether the exception will escape.
    """

    FAAS_TRIGGER = "faas.trigger"
    """
    Type of the trigger which caused this function execution.
    Note: For the server/consumer span on the incoming side,
`faas.trigger` MUST be set.

Clients invoking FaaS instances usually cannot set `faas.trigger`,
since they would typically need to look in the payload to determine
the event type. If clients set it, it should be the same as the
trigger that corresponding incoming would have (i.e., this has
nothing to do with the underlying transport used to make the API
call to invoke the lambda, which is often HTTP).
    """

    FAAS_EXECUTION = "faas.execution"
    """
    The execution ID of the current function execution.
    """

    FAAS_DOCUMENT_COLLECTION = "faas.document.collection"
    """
    The name of the source on which the triggering operation was performed. For example, in Cloud Storage or S3 corresponds to the bucket name, and in Cosmos DB to the database name.
    """

    FAAS_DOCUMENT_OPERATION = "faas.document.operation"
    """
    Describes the type of the operation that was performed on the data.
    """

    FAAS_DOCUMENT_TIME = "faas.document.time"
    """
    A string containing the time when the data was accessed in the [ISO 8601](https://www.iso.org/iso-8601-date-and-time-format.html) format expressed in [UTC](https://www.w3.org/TR/NOTE-datetime).
    """

    FAAS_DOCUMENT_NAME = "faas.document.name"
    """
    The document name/table subjected to the operation. For example, in Cloud Storage or S3 is the name of the file, and in Cosmos DB the table name.
    """

    HTTP_METHOD = "http.method"
    """
    HTTP request method.
    """

    HTTP_URL = "http.url"
    """
    Full HTTP request URL in the form `scheme://host[:port]/path?query[#fragment]`. Usually the fragment is not transmitted over HTTP, but if it is known, it should be included nevertheless.
    Note: `http.url` MUST NOT contain credentials passed via URL in form of `https://username:password@www.example.com/`. In such case the attribute's value should be `https://www.example.com/`.
    """

    HTTP_TARGET = "http.target"
    """
    The full request target as passed in a HTTP request line or equivalent.
    """

    HTTP_HOST = "http.host"
    """
    The value of the [HTTP host header](https://tools.ietf.org/html/rfc7230#section-5.4). An empty Host header should also be reported, see note.
    Note: When the header is present but empty the attribute SHOULD be set to the empty string. Note that this is a valid situation that is expected in certain cases, according the aforementioned [section of RFC 7230](https://tools.ietf.org/html/rfc7230#section-5.4). When the header is not set the attribute MUST NOT be set.
    """

    HTTP_SCHEME = "http.scheme"
    """
    The URI scheme identifying the used protocol.
    """

    HTTP_STATUS_CODE = "http.status_code"
    """
    [HTTP response status code](https://tools.ietf.org/html/rfc7231#section-6).
    """

    HTTP_FLAVOR = "http.flavor"
    """
    Kind of HTTP protocol used.
    Note: If `net.transport` is not specified, it can be assumed to be `IP.TCP` except if `http.flavor` is `QUIC`, in which case `IP.UDP` is assumed.
    """

    HTTP_USER_AGENT = "http.user_agent"
    """
    Value of the [HTTP User-Agent](https://tools.ietf.org/html/rfc7231#section-5.5.3) header sent by the client.
    """

    HTTP_REQUEST_CONTENT_LENGTH = "http.request_content_length"
    """
    The size of the request payload body in bytes. This is the number of bytes transferred excluding headers and is often, but not always, present as the [Content-Length](https://tools.ietf.org/html/rfc7230#section-3.3.2) header. For requests using transport encoding, this should be the compressed size.
    """

    HTTP_REQUEST_CONTENT_LENGTH_UNCOMPRESSED = (
        "http.request_content_length_uncompressed"
    )
    """
    The size of the uncompressed request payload body after transport decoding. Not set if transport encoding not used.
    """

    HTTP_RESPONSE_CONTENT_LENGTH = "http.response_content_length"
    """
    The size of the response payload body in bytes. This is the number of bytes transferred excluding headers and is often, but not always, present as the [Content-Length](https://tools.ietf.org/html/rfc7230#section-3.3.2) header. For requests using transport encoding, this should be the compressed size.
    """

    HTTP_RESPONSE_CONTENT_LENGTH_UNCOMPRESSED = (
        "http.response_content_length_uncompressed"
    )
    """
    The size of the uncompressed response payload body after transport decoding. Not set if transport encoding not used.
    """

    HTTP_RETRY_COUNT = "http.retry_count"
    """
    The ordinal number of request re-sending attempt.
    """

    HTTP_SERVER_NAME = "http.server_name"
    """
    The primary server name of the matched virtual host. This should be obtained via configuration. If no such configuration can be obtained, this attribute MUST NOT be set ( `net.host.name` should be used instead).
    Note: `http.url` is usually not readily available on the server side but would have to be assembled in a cumbersome and sometimes lossy process from other information (see e.g. open-telemetry/opentelemetry-python/pull/148). It is thus preferred to supply the raw data that is available.
    """

    HTTP_ROUTE = "http.route"
    """
    The matched route (path template).
    """

    HTTP_CLIENT_IP = "http.client_ip"
    """
    The IP address of the original client behind all proxies, if known (e.g. from [X-Forwarded-For](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For)).
    Note: This is not necessarily the same as `net.peer.ip`, which would
identify the network-level peer, which may be a proxy.

This attribute should be set when a source of information different
from the one used for `net.peer.ip`, is available even if that other
source just confirms the same value as `net.peer.ip`.
Rationale: For `net.peer.ip`, one typically does not know if it
comes from a proxy, reverse proxy, or the actual client. Setting
`http.client_ip` when it's the same as `net.peer.ip` means that
one is at least somewhat confident that the address is not that of
the closest proxy.
    """

    NET_HOST_IP = "net.host.ip"
    """
    Like `net.peer.ip` but for the host IP. Useful in case of a multi-IP host.
    """

    NET_HOST_PORT = "net.host.port"
    """
    Like `net.peer.port` but for the host port.
    """

    NET_HOST_NAME = "net.host.name"
    """
    Local hostname or similar, see note below.
    """

    NET_HOST_CONNECTION_TYPE = "net.host.connection.type"
    """
    The internet connection type currently being used by the host.
    """

    NET_HOST_CONNECTION_SUBTYPE = "net.host.connection.subtype"
    """
    This describes more details regarding the connection.type. It may be the type of cell technology connection, but it could be used for describing details about a wifi connection.
    """

    NET_HOST_CARRIER_NAME = "net.host.carrier.name"
    """
    The name of the mobile carrier.
    """

    NET_HOST_CARRIER_MCC = "net.host.carrier.mcc"
    """
    The mobile carrier country code.
    """

    NET_HOST_CARRIER_MNC = "net.host.carrier.mnc"
    """
    The mobile carrier network code.
    """

    NET_HOST_CARRIER_ICC = "net.host.carrier.icc"
    """
    The ISO 3166-1 alpha-2 2-character country code associated with the mobile carrier network.
    """

    MESSAGING_SYSTEM = "messaging.system"
    """
    A string identifying the messaging system.
    """

    MESSAGING_DESTINATION = "messaging.destination"
    """
    The message destination name. This might be equal to the span name but is required nevertheless.
    """

    MESSAGING_DESTINATION_KIND = "messaging.destination_kind"
    """
    The kind of message destination.
    """

    MESSAGING_TEMP_DESTINATION = "messaging.temp_destination"
    """
    A boolean that is true if the message destination is temporary.
    """

    MESSAGING_PROTOCOL = "messaging.protocol"
    """
    The name of the transport protocol.
    """

    MESSAGING_PROTOCOL_VERSION = "messaging.protocol_version"
    """
    The version of the transport protocol.
    """

    MESSAGING_URL = "messaging.url"
    """
    Connection string.
    """

    MESSAGING_MESSAGE_ID = "messaging.message_id"
    """
    A value used by the messaging system as an identifier for the message, represented as a string.
    """

    MESSAGING_CONVERSATION_ID = "messaging.conversation_id"
    """
    The [conversation ID](#conversations) identifying the conversation to which the message belongs, represented as a string. Sometimes called "Correlation ID".
    """

    MESSAGING_MESSAGE_PAYLOAD_SIZE_BYTES = (
        "messaging.message_payload_size_bytes"
    )
    """
    The (uncompressed) size of the message payload in bytes. Also use this attribute if it is unknown whether the compressed or uncompressed payload size is reported.
    """

    MESSAGING_MESSAGE_PAYLOAD_COMPRESSED_SIZE_BYTES = (
        "messaging.message_payload_compressed_size_bytes"
    )
    """
    The compressed size of the message payload in bytes.
    """

    FAAS_TIME = "faas.time"
    """
    A string containing the function invocation time in the [ISO 8601](https://www.iso.org/iso-8601-date-and-time-format.html) format expressed in [UTC](https://www.w3.org/TR/NOTE-datetime).
    """

    FAAS_CRON = "faas.cron"
    """
    A string containing the schedule period as [Cron Expression](https://docs.oracle.com/cd/E12058_01/doc/doc.1014/e12030/cron_expressions.htm).
    """

    FAAS_COLDSTART = "faas.coldstart"
    """
    A boolean that is true if the serverless function is executed for the first time (aka cold-start).
    """

    FAAS_INVOKED_NAME = "faas.invoked_name"
    """
    The name of the invoked function.
    Note: SHOULD be equal to the `faas.name` resource attribute of the invoked function.
    """

    FAAS_INVOKED_PROVIDER = "faas.invoked_provider"
    """
    The cloud provider of the invoked function.
    Note: SHOULD be equal to the `cloud.provider` resource attribute of the invoked function.
    """

    FAAS_INVOKED_REGION = "faas.invoked_region"
    """
    The cloud region of the invoked function.
    Note: SHOULD be equal to the `cloud.region` resource attribute of the invoked function.
    """

    PEER_SERVICE = "peer.service"
    """
    The [`service.name`](../../resource/semantic_conventions/README.md#service) of the remote service. SHOULD be equal to the actual `service.name` resource attribute of the remote service if any.
    """

    ENDUSER_ID = "enduser.id"
    """
    Username or client_id extracted from the access token or [Authorization](https://tools.ietf.org/html/rfc7235#section-4.2) header in the inbound request from outside the system.
    """

    ENDUSER_ROLE = "enduser.role"
    """
    Actual/assumed role the client is making the request under extracted from token or application security context.
    """

    ENDUSER_SCOPE = "enduser.scope"
    """
    Scopes or granted authorities the client currently possesses extracted from token or application security context. The value would come from the scope associated with an [OAuth 2.0 Access Token](https://tools.ietf.org/html/rfc6749#section-3.3) or an attribute value in a [SAML 2.0 Assertion](http://docs.oasis-open.org/security/saml/Post2.0/sstc-saml-tech-overview-2.0.html).
    """

    THREAD_ID = "thread.id"
    """
    Current "managed" thread ID (as opposed to OS thread ID).
    """

    THREAD_NAME = "thread.name"
    """
    Current thread name.
    """

    CODE_FUNCTION = "code.function"
    """
    The method or function name, or equivalent (usually rightmost part of the code unit's name).
    """

    CODE_NAMESPACE = "code.namespace"
    """
    The "namespace" within which `code.function` is defined. Usually the qualified class or module name, such that `code.namespace` + some separator + `code.function` form a unique identifier for the code unit.
    """

    CODE_FILEPATH = "code.filepath"
    """
    The source code file name that identifies the code unit as uniquely as possible (preferably an absolute file path).
    """

    CODE_LINENO = "code.lineno"
    """
    The line number in `code.filepath` best representing the operation. It SHOULD point within the code unit named in `code.function`.
    """

    RPC_SYSTEM = "rpc.system"
    """
    The value `aws-api`.
    """

    RPC_SERVICE = "rpc.service"
    """
    The name of the service to which a request is made, as returned by the AWS SDK.
    Note: This is the logical name of the service from the RPC interface perspective, which can be different from the name of any implementing class. The `code.namespace` attribute may be used to store the latter (despite the attribute name, it may include a class name; e.g., class with method actually executing the call on the server side, RPC client stub class on the client side).
    """

    RPC_METHOD = "rpc.method"
    """
    The name of the operation corresponding to the request, as returned by the AWS SDK.
    Note: This is the logical name of the method from the RPC interface perspective, which can be different from the name of any implementing method/function. The `code.function` attribute may be used to store the latter (e.g., method actually executing the call on the server side, RPC client stub method on the client side).
    """

    AWS_DYNAMODB_TABLE_NAMES = "aws.dynamodb.table_names"
    """
    The keys in the `RequestItems` object field.
    """

    AWS_DYNAMODB_CONSUMED_CAPACITY = "aws.dynamodb.consumed_capacity"
    """
    The JSON-serialized value of each item in the `ConsumedCapacity` response field.
    """

    AWS_DYNAMODB_ITEM_COLLECTION_METRICS = (
        "aws.dynamodb.item_collection_metrics"
    )
    """
    The JSON-serialized value of the `ItemCollectionMetrics` response field.
    """

    AWS_DYNAMODB_PROVISIONED_READ_CAPACITY = (
        "aws.dynamodb.provisioned_read_capacity"
    )
    """
    The value of the `ProvisionedThroughput.ReadCapacityUnits` request parameter.
    """

    AWS_DYNAMODB_PROVISIONED_WRITE_CAPACITY = (
        "aws.dynamodb.provisioned_write_capacity"
    )
    """
    The value of the `ProvisionedThroughput.WriteCapacityUnits` request parameter.
    """

    AWS_DYNAMODB_CONSISTENT_READ = "aws.dynamodb.consistent_read"
    """
    The value of the `ConsistentRead` request parameter.
    """

    AWS_DYNAMODB_PROJECTION = "aws.dynamodb.projection"
    """
    The value of the `ProjectionExpression` request parameter.
    """

    AWS_DYNAMODB_LIMIT = "aws.dynamodb.limit"
    """
    The value of the `Limit` request parameter.
    """

    AWS_DYNAMODB_ATTRIBUTES_TO_GET = "aws.dynamodb.attributes_to_get"
    """
    The value of the `AttributesToGet` request parameter.
    """

    AWS_DYNAMODB_INDEX_NAME = "aws.dynamodb.index_name"
    """
    The value of the `IndexName` request parameter.
    """

    AWS_DYNAMODB_SELECT = "aws.dynamodb.select"
    """
    The value of the `Select` request parameter.
    """

    AWS_DYNAMODB_GLOBAL_SECONDARY_INDEXES = (
        "aws.dynamodb.global_secondary_indexes"
    )
    """
    The JSON-serialized value of each item of the `GlobalSecondaryIndexes` request field.
    """

    AWS_DYNAMODB_LOCAL_SECONDARY_INDEXES = (
        "aws.dynamodb.local_secondary_indexes"
    )
    """
    The JSON-serialized value of each item of the `LocalSecondaryIndexes` request field.
    """

    AWS_DYNAMODB_EXCLUSIVE_START_TABLE = "aws.dynamodb.exclusive_start_table"
    """
    The value of the `ExclusiveStartTableName` request parameter.
    """

    AWS_DYNAMODB_TABLE_COUNT = "aws.dynamodb.table_count"
    """
    The the number of items in the `TableNames` response parameter.
    """

    AWS_DYNAMODB_SCAN_FORWARD = "aws.dynamodb.scan_forward"
    """
    The value of the `ScanIndexForward` request parameter.
    """

    AWS_DYNAMODB_SEGMENT = "aws.dynamodb.segment"
    """
    The value of the `Segment` request parameter.
    """

    AWS_DYNAMODB_TOTAL_SEGMENTS = "aws.dynamodb.total_segments"
    """
    The value of the `TotalSegments` request parameter.
    """

    AWS_DYNAMODB_COUNT = "aws.dynamodb.count"
    """
    The value of the `Count` response parameter.
    """

    AWS_DYNAMODB_SCANNED_COUNT = "aws.dynamodb.scanned_count"
    """
    The value of the `ScannedCount` response parameter.
    """

    AWS_DYNAMODB_ATTRIBUTE_DEFINITIONS = "aws.dynamodb.attribute_definitions"
    """
    The JSON-serialized value of each item in the `AttributeDefinitions` request field.
    """

    AWS_DYNAMODB_GLOBAL_SECONDARY_INDEX_UPDATES = (
        "aws.dynamodb.global_secondary_index_updates"
    )
    """
    The JSON-serialized value of each item in the the `GlobalSecondaryIndexUpdates` request field.
    """

    MESSAGING_OPERATION = "messaging.operation"
    """
    A string identifying the kind of message consumption as defined in the [Operation names](#operation-names) section above. If the operation is "send", this attribute MUST NOT be set, since the operation can be inferred from the span kind in that case.
    """

    MESSAGING_CONSUMER_ID = "messaging.consumer_id"
    """
    The identifier for the consumer receiving a message. For Kafka, set it to `{messaging.kafka.consumer_group} - {messaging.kafka.client_id}`, if both are present, or only `messaging.kafka.consumer_group`. For brokers, such as RabbitMQ and Artemis, set it to the `client_id` of the client consuming the message.
    """

    MESSAGING_RABBITMQ_ROUTING_KEY = "messaging.rabbitmq.routing_key"
    """
    RabbitMQ message routing key.
    """

    MESSAGING_KAFKA_MESSAGE_KEY = "messaging.kafka.message_key"
    """
    Message keys in Kafka are used for grouping alike messages to ensure they're processed on the same partition. They differ from `messaging.message_id` in that they're not unique. If the key is `null`, the attribute MUST NOT be set.
    Note: If the key type is not string, it's string representation has to be supplied for the attribute. If the key has no unambiguous, canonical string form, don't include its value.
    """

    MESSAGING_KAFKA_CONSUMER_GROUP = "messaging.kafka.consumer_group"
    """
    Name of the Kafka Consumer Group that is handling the message. Only applies to consumers, not producers.
    """

    MESSAGING_KAFKA_CLIENT_ID = "messaging.kafka.client_id"
    """
    Client Id for the Consumer or Producer that is handling the message.
    """

    MESSAGING_KAFKA_PARTITION = "messaging.kafka.partition"
    """
    Partition the message is sent to.
    """

    MESSAGING_KAFKA_TOMBSTONE = "messaging.kafka.tombstone"
    """
    A boolean that is true if the message is a tombstone.
    """

    MESSAGING_ROCKETMQ_NAMESPACE = "messaging.rocketmq.namespace"
    """
    Namespace of RocketMQ resources, resources in different namespaces are individual.
    """

    MESSAGING_ROCKETMQ_CLIENT_GROUP = "messaging.rocketmq.client_group"
    """
    Name of the RocketMQ producer/consumer group that is handling the message. The client type is identified by the SpanKind.
    """

    MESSAGING_ROCKETMQ_CLIENT_ID = "messaging.rocketmq.client_id"
    """
    The unique identifier for each client.
    """

    MESSAGING_ROCKETMQ_MESSAGE_TYPE = "messaging.rocketmq.message_type"
    """
    Type of message.
    """

    MESSAGING_ROCKETMQ_MESSAGE_TAG = "messaging.rocketmq.message_tag"
    """
    The secondary classifier of message besides topic.
    """

    MESSAGING_ROCKETMQ_MESSAGE_KEYS = "messaging.rocketmq.message_keys"
    """
    Key(s) of message, another way to mark message besides message id.
    """

    MESSAGING_ROCKETMQ_CONSUMPTION_MODEL = (
        "messaging.rocketmq.consumption_model"
    )
    """
    Model of message consumption. This only applies to consumer spans.
    """

    RPC_GRPC_STATUS_CODE = "rpc.grpc.status_code"
    """
    The [numeric status code](https://github.com/grpc/grpc/blob/v1.33.2/doc/statuscodes.md) of the gRPC request.
    """

    RPC_JSONRPC_VERSION = "rpc.jsonrpc.version"
    """
    Protocol version as in `jsonrpc` property of request/response. Since JSON-RPC 1.0 does not specify this, the value can be omitted.
    """

    RPC_JSONRPC_REQUEST_ID = "rpc.jsonrpc.request_id"
    """
    `id` property of request or response. Since protocol allows id to be int, string, `null` or missing (for notifications), value is expected to be cast to string for simplicity. Use empty string in case of `null` value. Omit entirely if this is a notification.
    """

    RPC_JSONRPC_ERROR_CODE = "rpc.jsonrpc.error_code"
    """
    `error.code` property of response if it is an error response.
    """

    RPC_JSONRPC_ERROR_MESSAGE = "rpc.jsonrpc.error_message"
    """
    `error.message` property of response if it is an error response.
    """

    MESSAGE_TYPE = "message.type"
    """
    Whether this is a received or sent message.
    """

    MESSAGE_ID = "message.id"
    """
    MUST be calculated as two different counters starting from `1` one for sent messages and one for received message.
    Note: This way we guarantee that the values will be consistent between different implementations.
    """

    MESSAGE_COMPRESSED_SIZE = "message.compressed_size"
    """
    Compressed size of the message in bytes.
    """

    MESSAGE_UNCOMPRESSED_SIZE = "message.uncompressed_size"
    """
    Uncompressed size of the message in bytes.
    """


class OpentracingRefTypeValues(Enum):
    CHILD_OF = "child_of"
    """The parent Span depends on the child Span in some capacity."""

    FOLLOWS_FROM = "follows_from"
    """The parent Span does not depend in any way on the result of the child Span."""


class DbSystemValues(Enum):
    OTHER_SQL = "other_sql"
    """Some other SQL database. Fallback only. See notes."""

    MSSQL = "mssql"
    """Microsoft SQL Server."""

    MYSQL = "mysql"
    """MySQL."""

    ORACLE = "oracle"
    """Oracle Database."""

    DB2 = "db2"
    """IBM Db2."""

    POSTGRESQL = "postgresql"
    """PostgreSQL."""

    REDSHIFT = "redshift"
    """Amazon Redshift."""

    HIVE = "hive"
    """Apache Hive."""

    CLOUDSCAPE = "cloudscape"
    """Cloudscape."""

    HSQLDB = "hsqldb"
    """HyperSQL DataBase."""

    PROGRESS = "progress"
    """Progress Database."""

    MAXDB = "maxdb"
    """SAP MaxDB."""

    HANADB = "hanadb"
    """SAP HANA."""

    INGRES = "ingres"
    """Ingres."""

    FIRSTSQL = "firstsql"
    """FirstSQL."""

    EDB = "edb"
    """EnterpriseDB."""

    CACHE = "cache"
    """InterSystems Caché."""

    ADABAS = "adabas"
    """Adabas (Adaptable Database System)."""

    FIREBIRD = "firebird"
    """Firebird."""

    DERBY = "derby"
    """Apache Derby."""

    FILEMAKER = "filemaker"
    """FileMaker."""

    INFORMIX = "informix"
    """Informix."""

    INSTANTDB = "instantdb"
    """InstantDB."""

    INTERBASE = "interbase"
    """InterBase."""

    MARIADB = "mariadb"
    """MariaDB."""

    NETEZZA = "netezza"
    """Netezza."""

    PERVASIVE = "pervasive"
    """Pervasive PSQL."""

    POINTBASE = "pointbase"
    """PointBase."""

    SQLITE = "sqlite"
    """SQLite."""

    SYBASE = "sybase"
    """Sybase."""

    TERADATA = "teradata"
    """Teradata."""

    VERTICA = "vertica"
    """Vertica."""

    H2 = "h2"
    """H2."""

    COLDFUSION = "coldfusion"
    """ColdFusion IMQ."""

    CASSANDRA = "cassandra"
    """Apache Cassandra."""

    HBASE = "hbase"
    """Apache HBase."""

    MONGODB = "mongodb"
    """MongoDB."""

    REDIS = "redis"
    """Redis."""

    COUCHBASE = "couchbase"
    """Couchbase."""

    COUCHDB = "couchdb"
    """CouchDB."""

    COSMOSDB = "cosmosdb"
    """Microsoft Azure Cosmos DB."""

    DYNAMODB = "dynamodb"
    """Amazon DynamoDB."""

    NEO4J = "neo4j"
    """Neo4j."""

    GEODE = "geode"
    """Apache Geode."""

    ELASTICSEARCH = "elasticsearch"
    """Elasticsearch."""

    MEMCACHED = "memcached"
    """Memcached."""

    COCKROACHDB = "cockroachdb"
    """CockroachDB."""


class NetTransportValues(Enum):
    IP_TCP = "ip_tcp"
    """ip_tcp."""

    IP_UDP = "ip_udp"
    """ip_udp."""

    IP = "ip"
    """Another IP-based protocol."""

    UNIX = "unix"
    """Unix Domain socket. See below."""

    PIPE = "pipe"
    """Named or anonymous pipe. See note below."""

    INPROC = "inproc"
    """In-process communication."""

    OTHER = "other"
    """Something else (non IP-based)."""


class DbCassandraConsistencyLevelValues(Enum):
    ALL = "all"
    """all."""

    EACH_QUORUM = "each_quorum"
    """each_quorum."""

    QUORUM = "quorum"
    """quorum."""

    LOCAL_QUORUM = "local_quorum"
    """local_quorum."""

    ONE = "one"
    """one."""

    TWO = "two"
    """two."""

    THREE = "three"
    """three."""

    LOCAL_ONE = "local_one"
    """local_one."""

    ANY = "any"
    """any."""

    SERIAL = "serial"
    """serial."""

    LOCAL_SERIAL = "local_serial"
    """local_serial."""


class FaasTriggerValues(Enum):
    DATASOURCE = "datasource"
    """A response to some data source operation such as a database or filesystem read/write."""

    HTTP = "http"
    """To provide an answer to an inbound HTTP request."""

    PUBSUB = "pubsub"
    """A function is set to be executed when messages are sent to a messaging system."""

    TIMER = "timer"
    """A function is scheduled to be executed regularly."""

    OTHER = "other"
    """If none of the others apply."""


class FaasDocumentOperationValues(Enum):
    INSERT = "insert"
    """When a new object is created."""

    EDIT = "edit"
    """When an object is modified."""

    DELETE = "delete"
    """When an object is deleted."""


class HttpFlavorValues(Enum):
    HTTP_1_0 = "1.0"
    """HTTP/1.0."""

    HTTP_1_1 = "1.1"
    """HTTP/1.1."""

    HTTP_2_0 = "2.0"
    """HTTP/2."""

    HTTP_3_0 = "3.0"
    """HTTP/3."""

    SPDY = "SPDY"
    """SPDY protocol."""

    QUIC = "QUIC"
    """QUIC protocol."""


class NetHostConnectionTypeValues(Enum):
    WIFI = "wifi"
    """wifi."""

    WIRED = "wired"
    """wired."""

    CELL = "cell"
    """cell."""

    UNAVAILABLE = "unavailable"
    """unavailable."""

    UNKNOWN = "unknown"
    """unknown."""


class NetHostConnectionSubtypeValues(Enum):
    GPRS = "gprs"
    """GPRS."""

    EDGE = "edge"
    """EDGE."""

    UMTS = "umts"
    """UMTS."""

    CDMA = "cdma"
    """CDMA."""

    EVDO_0 = "evdo_0"
    """EVDO Rel. 0."""

    EVDO_A = "evdo_a"
    """EVDO Rev. A."""

    CDMA2000_1XRTT = "cdma2000_1xrtt"
    """CDMA2000 1XRTT."""

    HSDPA = "hsdpa"
    """HSDPA."""

    HSUPA = "hsupa"
    """HSUPA."""

    HSPA = "hspa"
    """HSPA."""

    IDEN = "iden"
    """IDEN."""

    EVDO_B = "evdo_b"
    """EVDO Rev. B."""

    LTE = "lte"
    """LTE."""

    EHRPD = "ehrpd"
    """EHRPD."""

    HSPAP = "hspap"
    """HSPAP."""

    GSM = "gsm"
    """GSM."""

    TD_SCDMA = "td_scdma"
    """TD-SCDMA."""

    IWLAN = "iwlan"
    """IWLAN."""

    NR = "nr"
    """5G NR (New Radio)."""

    NRNSA = "nrnsa"
    """5G NRNSA (New Radio Non-Standalone)."""

    LTE_CA = "lte_ca"
    """LTE CA."""


class MessagingDestinationKindValues(Enum):
    QUEUE = "queue"
    """A message sent to a queue."""

    TOPIC = "topic"
    """A message sent to a topic."""


class FaasInvokedProviderValues(Enum):
    ALIBABA_CLOUD = "alibaba_cloud"
    """Alibaba Cloud."""

    AWS = "aws"
    """Amazon Web Services."""

    AZURE = "azure"
    """Microsoft Azure."""

    GCP = "gcp"
    """Google Cloud Platform."""

    TENCENT_CLOUD = "tencent_cloud"
    """Tencent Cloud."""


class RpcSystemValues(Enum):
    GRPC = "grpc"
    """gRPC."""

    JAVA_RMI = "java_rmi"
    """Java RMI."""

    DOTNET_WCF = "dotnet_wcf"
    """.NET WCF."""

    APACHE_DUBBO = "apache_dubbo"
    """Apache Dubbo."""


class MessagingOperationValues(Enum):
    RECEIVE = "receive"
    """receive."""

    PROCESS = "process"
    """process."""


class MessagingRocketmqMessageTypeValues(Enum):
    NORMAL = "normal"
    """Normal message."""

    FIFO = "fifo"
    """FIFO message."""

    DELAY = "delay"
    """Delay message."""

    TRANSACTION = "transaction"
    """Transaction message."""


class MessagingRocketmqConsumptionModelValues(Enum):
    CLUSTERING = "clustering"
    """Clustering consumption model."""

    BROADCASTING = "broadcasting"
    """Broadcasting consumption model."""


class RpcGrpcStatusCodeValues(Enum):
    OK = 0
    """OK."""

    CANCELLED = 1
    """CANCELLED."""

    UNKNOWN = 2
    """UNKNOWN."""

    INVALID_ARGUMENT = 3
    """INVALID_ARGUMENT."""

    DEADLINE_EXCEEDED = 4
    """DEADLINE_EXCEEDED."""

    NOT_FOUND = 5
    """NOT_FOUND."""

    ALREADY_EXISTS = 6
    """ALREADY_EXISTS."""

    PERMISSION_DENIED = 7
    """PERMISSION_DENIED."""

    RESOURCE_EXHAUSTED = 8
    """RESOURCE_EXHAUSTED."""

    FAILED_PRECONDITION = 9
    """FAILED_PRECONDITION."""

    ABORTED = 10
    """ABORTED."""

    OUT_OF_RANGE = 11
    """OUT_OF_RANGE."""

    UNIMPLEMENTED = 12
    """UNIMPLEMENTED."""

    INTERNAL = 13
    """INTERNAL."""

    UNAVAILABLE = 14
    """UNAVAILABLE."""

    DATA_LOSS = 15
    """DATA_LOSS."""

    UNAUTHENTICATED = 16
    """UNAUTHENTICATED."""


class MessageTypeValues(Enum):
    SENT = "SENT"
    """sent."""

    RECEIVED = "RECEIVED"
    """received."""
