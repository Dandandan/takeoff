import logging

from azure.mgmt.applicationinsights import ApplicationInsightsManagementClient
from azure.mgmt.applicationinsights.models import ApplicationInsightsComponent

from runway.ApplicationVersion import ApplicationVersion
from runway.DeploymentStep import DeploymentStep
from runway.create_databricks_secrets import CreateDatabricksSecrets
from runway.credentials.KeyVaultCredentialsMixin import Secret
from runway.credentials.azure_active_directory_user import AzureUserCredentials
from runway.credentials.azure_databricks import Databricks
from runway.credentials.azure_subscription_id import AzureSubscriptionId
from runway.util import get_application_name

logger = logging.getLogger(__name__)


class CreateApplicationInsights(DeploymentStep):
    def __init__(self, env: ApplicationVersion, config: dict):
        super().__init__(env, config)

    def create_application_insights(self, kind: str, application_type: str) -> ApplicationInsightsComponent:

        # Check some values
        if kind not in {"web", "ios", "other", "store", "java", "phone"}:
            raise ValueError("Unknown application insights kind: {}".format(kind))

        if application_type not in {"web", "other"}:
            raise ValueError("Unknown application insights application_type: {}".format(application_type))

        application_name = get_application_name()
        client = self.__create_client()

        insight = self.__find(client, application_name)
        if not insight:
            logger.info("Creating new Application Insights...")
            # Create a new Application Insights
            comp = ApplicationInsightsComponent(
                location=self.config["runway_azure"]["location"], kind=kind, application_type=application_type
            )
            insight = client.components.create_or_update(
                f"sdh{self.env.environment.lower()}", application_name, comp
            )
        return insight

    def __create_client(self) -> ApplicationInsightsManagementClient:
        azure_user_credentials = AzureUserCredentials(
            vault_name=self.vault_name, vault_client=self.vault_client
        ).credentials(self.config)

        return ApplicationInsightsManagementClient(
            azure_user_credentials,
            AzureSubscriptionId(self.vault_name, self.vault_client).subscription_id(self.config),
        )

    def __find(self, client: ApplicationInsightsManagementClient, name: str):
        for insight in client.components.list():
            if insight.name == name:
                return insight
        return None


class CreateDatabricksApplicationInsights(CreateApplicationInsights):
    def run(self):
        self.create_databricks_application_insights()

    def create_databricks_application_insights(self):
        application_name = get_application_name()
        insight = self.create_application_insights("other", "other")

        instrumentation_secret = Secret("instrumentation-key", insight.instrumentation_key)

        databricks_client = Databricks(self.vault_name, self.vault_client).api_client(self.config)

        CreateDatabricksSecrets._create_scope(databricks_client, application_name)
        CreateDatabricksSecrets._add_secrets(databricks_client, application_name, [instrumentation_secret])
