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

from enum import Enum


class ResourceAttributes:
    CLOUD_PROVIDER = "cloud.provider"
    """
    Name of the cloud provider.
    """

    CLOUD_ACCOUNT_ID = "cloud.account.id"
    """
    The cloud account ID the resource is assigned to.
    """

    CLOUD_REGION = "cloud.region"
    """
    The geographical region the resource is running.
    Note: Refer to your provider's docs to see the available regions, for example [Alibaba Cloud regions](https://www.alibabacloud.com/help/doc-detail/40654.htm), [AWS regions](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/), [Azure regions](https://azure.microsoft.com/en-us/global-infrastructure/geographies/), [Google Cloud regions](https://cloud.google.com/about/locations), or [Tencent Cloud regions](https://intl.cloud.tencent.com/document/product/213/6091).
    """

    CLOUD_AVAILABILITY_ZONE = "cloud.availability_zone"
    """
    Cloud regions often have multiple, isolated locations known as zones to increase availability. Availability zone represents the zone where the resource is running.
    Note: Availability zones are called "zones" on Alibaba Cloud and Google Cloud.
    """

    CLOUD_PLATFORM = "cloud.platform"
    """
    The cloud platform in use.
    Note: The prefix of the service SHOULD match the one specified in `cloud.provider`.
    """

    AWS_ECS_CONTAINER_ARN = "aws.ecs.container.arn"
    """
    The Amazon Resource Name (ARN) of an [ECS container instance](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_instances.html).
    """

    AWS_ECS_CLUSTER_ARN = "aws.ecs.cluster.arn"
    """
    The ARN of an [ECS cluster](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/clusters.html).
    """

    AWS_ECS_LAUNCHTYPE = "aws.ecs.launchtype"
    """
    The [launch type](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/launch_types.html) for an ECS task.
    """

    AWS_ECS_TASK_ARN = "aws.ecs.task.arn"
    """
    The ARN of an [ECS task definition](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html).
    """

    AWS_ECS_TASK_FAMILY = "aws.ecs.task.family"
    """
    The task definition family this task definition is a member of.
    """

    AWS_ECS_TASK_REVISION = "aws.ecs.task.revision"
    """
    The revision for this task definition.
    """

    AWS_EKS_CLUSTER_ARN = "aws.eks.cluster.arn"
    """
    The ARN of an EKS cluster.
    """

    AWS_LOG_GROUP_NAMES = "aws.log.group.names"
    """
    The name(s) of the AWS log group(s) an application is writing to.
    Note: Multiple log groups must be supported for cases like multi-container applications, where a single application has sidecar containers, and each write to their own log group.
    """

    AWS_LOG_GROUP_ARNS = "aws.log.group.arns"
    """
    The Amazon Resource Name(s) (ARN) of the AWS log group(s).
    Note: See the [log group ARN format documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/iam-access-control-overview-cwl.html#CWL_ARN_Format).
    """

    AWS_LOG_STREAM_NAMES = "aws.log.stream.names"
    """
    The name(s) of the AWS log stream(s) an application is writing to.
    """

    AWS_LOG_STREAM_ARNS = "aws.log.stream.arns"
    """
    The ARN(s) of the AWS log stream(s).
    Note: See the [log stream ARN format documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/iam-access-control-overview-cwl.html#CWL_ARN_Format). One log group can contain several log streams, so these ARNs necessarily identify both a log group and a log stream.
    """

    CONTAINER_NAME = "container.name"
    """
    Container name used by container runtime.
    """

    CONTAINER_ID = "container.id"
    """
    Container ID. Usually a UUID, as for example used to [identify Docker containers](https://docs.docker.com/engine/reference/run/#container-identification). The UUID might be abbreviated.
    """

    CONTAINER_RUNTIME = "container.runtime"
    """
    The container runtime managing this container.
    """

    CONTAINER_IMAGE_NAME = "container.image.name"
    """
    Name of the image the container was built on.
    """

    CONTAINER_IMAGE_TAG = "container.image.tag"
    """
    Container image tag.
    """

    DEPLOYMENT_ENVIRONMENT = "deployment.environment"
    """
    Name of the [deployment environment](https://en.wikipedia.org/wiki/Deployment_environment) (aka deployment tier).
    """

    DEVICE_ID = "device.id"
    """
    A unique identifier representing the device.
    Note: The device identifier MUST only be defined using the values outlined below. This value is not an advertising identifier and MUST NOT be used as such. On iOS (Swift or Objective-C), this value MUST be equal to the [vendor identifier](https://developer.apple.com/documentation/uikit/uidevice/1620059-identifierforvendor). On Android (Java or Kotlin), this value MUST be equal to the Firebase Installation ID or a globally unique UUID which is persisted across sessions in your application. More information can be found [here](https://developer.android.com/training/articles/user-data-ids) on best practices and exact implementation details. Caution should be taken when storing personal data or anything which can identify a user. GDPR and data protection laws may apply, ensure you do your own due diligence.
    """

    DEVICE_MODEL_IDENTIFIER = "device.model.identifier"
    """
    The model identifier for the device.
    Note: It's recommended this value represents a machine readable version of the model identifier rather than the market or consumer-friendly name of the device.
    """

    DEVICE_MODEL_NAME = "device.model.name"
    """
    The marketing name for the device model.
    Note: It's recommended this value represents a human readable version of the device model rather than a machine readable alternative.
    """

    DEVICE_MANUFACTURER = "device.manufacturer"
    """
    The name of the device manufacturer.
    Note: The Android OS provides this field via [Build](https://developer.android.com/reference/android/os/Build#MANUFACTURER). iOS apps SHOULD hardcode the value `Apple`.
    """

    FAAS_NAME = "faas.name"
    """
    The name of the single function that this runtime instance executes.
    Note: This is the name of the function as configured/deployed on the FaaS platform and is usually different from the name of the callback function (which may be stored in the [`code.namespace`/`code.function`](../../trace/semantic_conventions/span-general.md#source-code-attributes) span attributes).
    """

    FAAS_ID = "faas.id"
    """
    The unique ID of the single function that this runtime instance executes.
    Note: Depending on the cloud provider, use:

* **AWS Lambda:** The function [ARN](https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html).
Take care not to use the "invoked ARN" directly but replace any
[alias suffix](https://docs.aws.amazon.com/lambda/latest/dg/configuration-aliases.html) with the resolved function version, as the same runtime instance may be invocable with multiple
different aliases.
* **GCP:** The [URI of the resource](https://cloud.google.com/iam/docs/full-resource-names)
* **Azure:** The [Fully Qualified Resource ID](https://docs.microsoft.com/en-us/rest/api/resources/resources/get-by-id).

On some providers, it may not be possible to determine the full ID at startup,
which is why this field cannot be made required. For example, on AWS the account ID
part of the ARN is not available without calling another AWS API
which may be deemed too slow for a short-running lambda function.
As an alternative, consider setting `faas.id` as a span attribute instead.
    """

    FAAS_VERSION = "faas.version"
    """
    The immutable version of the function being executed.
    Note: Depending on the cloud provider and platform, use:

* **AWS Lambda:** The [function version](https://docs.aws.amazon.com/lambda/latest/dg/configuration-versions.html)
  (an integer represented as a decimal string).
* **Google Cloud Run:** The [revision](https://cloud.google.com/run/docs/managing/revisions)
  (i.e., the function name plus the revision suffix).
* **Google Cloud Functions:** The value of the
  [`K_REVISION` environment variable](https://cloud.google.com/functions/docs/env-var#runtime_environment_variables_set_automatically).
* **Azure Functions:** Not applicable. Do not set this attribute.
    """

    FAAS_INSTANCE = "faas.instance"
    """
    The execution environment ID as a string, that will be potentially reused for other invocations to the same function/function version.
    Note: * **AWS Lambda:** Use the (full) log stream name.
    """

    FAAS_MAX_MEMORY = "faas.max_memory"
    """
    The amount of memory available to the serverless function in MiB.
    Note: It's recommended to set this attribute since e.g. too little memory can easily stop a Java AWS Lambda function from working correctly. On AWS Lambda, the environment variable `AWS_LAMBDA_FUNCTION_MEMORY_SIZE` provides this information.
    """

    HOST_ID = "host.id"
    """
    Unique host ID. For Cloud, this must be the instance_id assigned by the cloud provider.
    """

    HOST_NAME = "host.name"
    """
    Name of the host. On Unix systems, it may contain what the hostname command returns, or the fully qualified hostname, or another name specified by the user.
    """

    HOST_TYPE = "host.type"
    """
    Type of host. For Cloud, this must be the machine type.
    """

    HOST_ARCH = "host.arch"
    """
    The CPU architecture the host system is running on.
    """

    HOST_IMAGE_NAME = "host.image.name"
    """
    Name of the VM image or OS install the host was instantiated from.
    """

    HOST_IMAGE_ID = "host.image.id"
    """
    VM image ID. For Cloud, this value is from the provider.
    """

    HOST_IMAGE_VERSION = "host.image.version"
    """
    The version string of the VM image as defined in [Version Attributes](README.md#version-attributes).
    """

    K8S_CLUSTER_NAME = "k8s.cluster.name"
    """
    The name of the cluster.
    """

    K8S_NODE_NAME = "k8s.node.name"
    """
    The name of the Node.
    """

    K8S_NODE_UID = "k8s.node.uid"
    """
    The UID of the Node.
    """

    K8S_NAMESPACE_NAME = "k8s.namespace.name"
    """
    The name of the namespace that the pod is running in.
    """

    K8S_POD_UID = "k8s.pod.uid"
    """
    The UID of the Pod.
    """

    K8S_POD_NAME = "k8s.pod.name"
    """
    The name of the Pod.
    """

    K8S_CONTAINER_NAME = "k8s.container.name"
    """
    The name of the Container from Pod specification, must be unique within a Pod. Container runtime usually uses different globally unique name (`container.name`).
    """

    K8S_CONTAINER_RESTART_COUNT = "k8s.container.restart_count"
    """
    Number of times the container was restarted. This attribute can be used to identify a particular container (running or stopped) within a container spec.
    """

    K8S_REPLICASET_UID = "k8s.replicaset.uid"
    """
    The UID of the ReplicaSet.
    """

    K8S_REPLICASET_NAME = "k8s.replicaset.name"
    """
    The name of the ReplicaSet.
    """

    K8S_DEPLOYMENT_UID = "k8s.deployment.uid"
    """
    The UID of the Deployment.
    """

    K8S_DEPLOYMENT_NAME = "k8s.deployment.name"
    """
    The name of the Deployment.
    """

    K8S_STATEFULSET_UID = "k8s.statefulset.uid"
    """
    The UID of the StatefulSet.
    """

    K8S_STATEFULSET_NAME = "k8s.statefulset.name"
    """
    The name of the StatefulSet.
    """

    K8S_DAEMONSET_UID = "k8s.daemonset.uid"
    """
    The UID of the DaemonSet.
    """

    K8S_DAEMONSET_NAME = "k8s.daemonset.name"
    """
    The name of the DaemonSet.
    """

    K8S_JOB_UID = "k8s.job.uid"
    """
    The UID of the Job.
    """

    K8S_JOB_NAME = "k8s.job.name"
    """
    The name of the Job.
    """

    K8S_CRONJOB_UID = "k8s.cronjob.uid"
    """
    The UID of the CronJob.
    """

    K8S_CRONJOB_NAME = "k8s.cronjob.name"
    """
    The name of the CronJob.
    """

    OS_TYPE = "os.type"
    """
    The operating system type.
    """

    OS_DESCRIPTION = "os.description"
    """
    Human readable (not intended to be parsed) OS version information, like e.g. reported by `ver` or `lsb_release -a` commands.
    """

    OS_NAME = "os.name"
    """
    Human readable operating system name.
    """

    OS_VERSION = "os.version"
    """
    The version string of the operating system as defined in [Version Attributes](../../resource/semantic_conventions/README.md#version-attributes).
    """

    PROCESS_PID = "process.pid"
    """
    Process identifier (PID).
    """

    PROCESS_EXECUTABLE_NAME = "process.executable.name"
    """
    The name of the process executable. On Linux based systems, can be set to the `Name` in `proc/[pid]/status`. On Windows, can be set to the base name of `GetProcessImageFileNameW`.
    """

    PROCESS_EXECUTABLE_PATH = "process.executable.path"
    """
    The full path to the process executable. On Linux based systems, can be set to the target of `proc/[pid]/exe`. On Windows, can be set to the result of `GetProcessImageFileNameW`.
    """

    PROCESS_COMMAND = "process.command"
    """
    The command used to launch the process (i.e. the command name). On Linux based systems, can be set to the zeroth string in `proc/[pid]/cmdline`. On Windows, can be set to the first parameter extracted from `GetCommandLineW`.
    """

    PROCESS_COMMAND_LINE = "process.command_line"
    """
    The full command used to launch the process as a single string representing the full command. On Windows, can be set to the result of `GetCommandLineW`. Do not set this if you have to assemble it just for monitoring; use `process.command_args` instead.
    """

    PROCESS_COMMAND_ARGS = "process.command_args"
    """
    All the command arguments (including the command/executable itself) as received by the process. On Linux-based systems (and some other Unixoid systems supporting procfs), can be set according to the list of null-delimited strings extracted from `proc/[pid]/cmdline`. For libc-based executables, this would be the full argv vector passed to `main`.
    """

    PROCESS_OWNER = "process.owner"
    """
    The username of the user that owns the process.
    """

    PROCESS_RUNTIME_NAME = "process.runtime.name"
    """
    The name of the runtime of this process. For compiled native binaries, this SHOULD be the name of the compiler.
    """

    PROCESS_RUNTIME_VERSION = "process.runtime.version"
    """
    The version of the runtime of this process, as returned by the runtime without modification.
    """

    PROCESS_RUNTIME_DESCRIPTION = "process.runtime.description"
    """
    An additional description about the runtime of the process, for example a specific vendor customization of the runtime environment.
    """

    SERVICE_NAME = "service.name"
    """
    Logical name of the service.
    Note: MUST be the same for all instances of horizontally scaled services. If the value was not specified, SDKs MUST fallback to `unknown_service:` concatenated with [`process.executable.name`](process.md#process), e.g. `unknown_service:bash`. If `process.executable.name` is not available, the value MUST be set to `unknown_service`.
    """

    SERVICE_NAMESPACE = "service.namespace"
    """
    A namespace for `service.name`.
    Note: A string value having a meaning that helps to distinguish a group of services, for example the team name that owns a group of services. `service.name` is expected to be unique within the same namespace. If `service.namespace` is not specified in the Resource then `service.name` is expected to be unique for all services that have no explicit namespace defined (so the empty/unspecified namespace is simply one more valid namespace). Zero-length namespace string is assumed equal to unspecified namespace.
    """

    SERVICE_INSTANCE_ID = "service.instance.id"
    """
    The string ID of the service instance.
    Note: MUST be unique for each instance of the same `service.namespace,service.name` pair (in other words `service.namespace,service.name,service.instance.id` triplet MUST be globally unique). The ID helps to distinguish instances of the same service that exist at the same time (e.g. instances of a horizontally scaled service). It is preferable for the ID to be persistent and stay the same for the lifetime of the service instance, however it is acceptable that the ID is ephemeral and changes during important lifetime events for the service (e.g. service restarts). If the service has no inherent unique ID that can be used as the value of this attribute it is recommended to generate a random Version 1 or Version 4 RFC 4122 UUID (services aiming for reproducible UUIDs may also use Version 5, see RFC 4122 for more recommendations).
    """

    SERVICE_VERSION = "service.version"
    """
    The version string of the service API or implementation.
    """

    TELEMETRY_SDK_NAME = "telemetry.sdk.name"
    """
    The name of the telemetry SDK as defined above.
    """

    TELEMETRY_SDK_LANGUAGE = "telemetry.sdk.language"
    """
    The language of the telemetry SDK.
    """

    TELEMETRY_SDK_VERSION = "telemetry.sdk.version"
    """
    The version string of the telemetry SDK.
    """

    TELEMETRY_AUTO_VERSION = "telemetry.auto.version"
    """
    The version string of the auto instrumentation agent, if used.
    """

    WEBENGINE_NAME = "webengine.name"
    """
    The name of the web engine.
    """

    WEBENGINE_VERSION = "webengine.version"
    """
    The version of the web engine.
    """

    WEBENGINE_DESCRIPTION = "webengine.description"
    """
    Additional description of the web engine (e.g. detailed version and edition information).
    """


class CloudProviderValues(Enum):
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


class CloudPlatformValues(Enum):
    ALIBABA_CLOUD_ECS = "alibaba_cloud_ecs"
    """Alibaba Cloud Elastic Compute Service."""

    ALIBABA_CLOUD_FC = "alibaba_cloud_fc"
    """Alibaba Cloud Function Compute."""

    AWS_EC2 = "aws_ec2"
    """AWS Elastic Compute Cloud."""

    AWS_ECS = "aws_ecs"
    """AWS Elastic Container Service."""

    AWS_EKS = "aws_eks"
    """AWS Elastic Kubernetes Service."""

    AWS_LAMBDA = "aws_lambda"
    """AWS Lambda."""

    AWS_ELASTIC_BEANSTALK = "aws_elastic_beanstalk"
    """AWS Elastic Beanstalk."""

    AWS_APP_RUNNER = "aws_app_runner"
    """AWS App Runner."""

    AZURE_VM = "azure_vm"
    """Azure Virtual Machines."""

    AZURE_CONTAINER_INSTANCES = "azure_container_instances"
    """Azure Container Instances."""

    AZURE_AKS = "azure_aks"
    """Azure Kubernetes Service."""

    AZURE_FUNCTIONS = "azure_functions"
    """Azure Functions."""

    AZURE_APP_SERVICE = "azure_app_service"
    """Azure App Service."""

    GCP_COMPUTE_ENGINE = "gcp_compute_engine"
    """Google Cloud Compute Engine (GCE)."""

    GCP_CLOUD_RUN = "gcp_cloud_run"
    """Google Cloud Run."""

    GCP_KUBERNETES_ENGINE = "gcp_kubernetes_engine"
    """Google Cloud Kubernetes Engine (GKE)."""

    GCP_CLOUD_FUNCTIONS = "gcp_cloud_functions"
    """Google Cloud Functions (GCF)."""

    GCP_APP_ENGINE = "gcp_app_engine"
    """Google Cloud App Engine (GAE)."""

    TENCENT_CLOUD_CVM = "tencent_cloud_cvm"
    """Tencent Cloud Cloud Virtual Machine (CVM)."""

    TENCENT_CLOUD_EKS = "tencent_cloud_eks"
    """Tencent Cloud Elastic Kubernetes Service (EKS)."""

    TENCENT_CLOUD_SCF = "tencent_cloud_scf"
    """Tencent Cloud Serverless Cloud Function (SCF)."""


class AwsEcsLaunchtypeValues(Enum):
    EC2 = "ec2"
    """ec2."""

    FARGATE = "fargate"
    """fargate."""


class HostArchValues(Enum):
    AMD64 = "amd64"
    """AMD64."""

    ARM32 = "arm32"
    """ARM32."""

    ARM64 = "arm64"
    """ARM64."""

    IA64 = "ia64"
    """Itanium."""

    PPC32 = "ppc32"
    """32-bit PowerPC."""

    PPC64 = "ppc64"
    """64-bit PowerPC."""

    S390X = "s390x"
    """IBM z/Architecture."""

    X86 = "x86"
    """32-bit x86."""


class OsTypeValues(Enum):
    WINDOWS = "windows"
    """Microsoft Windows."""

    LINUX = "linux"
    """Linux."""

    DARWIN = "darwin"
    """Apple Darwin."""

    FREEBSD = "freebsd"
    """FreeBSD."""

    NETBSD = "netbsd"
    """NetBSD."""

    OPENBSD = "openbsd"
    """OpenBSD."""

    DRAGONFLYBSD = "dragonflybsd"
    """DragonFly BSD."""

    HPUX = "hpux"
    """HP-UX (Hewlett Packard Unix)."""

    AIX = "aix"
    """AIX (Advanced Interactive eXecutive)."""

    SOLARIS = "solaris"
    """SunOS, Oracle Solaris."""

    Z_OS = "z_os"
    """IBM z/OS."""


class TelemetrySdkLanguageValues(Enum):
    CPP = "cpp"
    """cpp."""

    DOTNET = "dotnet"
    """dotnet."""

    ERLANG = "erlang"
    """erlang."""

    GO = "go"
    """go."""

    JAVA = "java"
    """java."""

    NODEJS = "nodejs"
    """nodejs."""

    PHP = "php"
    """php."""

    PYTHON = "python"
    """python."""

    RUBY = "ruby"
    """ruby."""

    WEBJS = "webjs"
    """webjs."""

    SWIFT = "swift"
    """swift."""
