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


class MetricInstruments:

    HTTP_SERVER_DURATION = "http.server.duration"

    HTTP_SERVER_REQUEST_SIZE = "http.server.request.size"

    HTTP_SERVER_RESPONSE_SIZE = "http.server.response.size"

    HTTP_SERVER_ACTIVE_REQUESTS = "http.server.active_requests"

    HTTP_CLIENT_DURATION = "http.client.duration"

    HTTP_CLIENT_REQUEST_SIZE = "http.client.request.size"

    HTTP_CLIENT_RESPONSE_SIZE = "http.client.response.size"

    DB_CLIENT_CONNECTIONS_USAGE = "db.client.connections.usage"
