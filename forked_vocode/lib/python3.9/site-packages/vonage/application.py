from deprecated import deprecated


@deprecated(
    version='3.0.0',
    reason='Renamed to Application as V1 is out of support and this new \
    naming is in line with other APIs. Please use Application instead.',
)
class ApplicationV2:
    auth_type = 'header'

    def __init__(self, client):
        self._client = client

    def create_application(self, application_data):
        """
        Create an application using the provided `application_data`.

        :param dict application_data: A JSON-style dict describing the application to be created.

        >>> client.application.create_application({ 'name': 'My Cool App!' })

        Details of the `application_data` dict are described at https://developer.vonage.com/api/application.v2#createApplication
        """
        return self._client.post(
            self._client.api_host(),
            "/v2/applications",
            application_data,
            auth_type=ApplicationV2.auth_type,
        )

    def get_application(self, application_id):
        """
        Get application details for the application with `application_id`.

        The format of the returned dict is described at https://developer.vonage.com/api/application.v2#getApplication

        :param str application_id: The application ID.
        :rtype: dict
        """

        return self._client.get(
            self._client.api_host(),
            f"/v2/applications/{application_id}",
            auth_type=ApplicationV2.auth_type,
        )

    def update_application(self, application_id, params):
        """
        Update the application with `application_id` using the values provided in `params`.


        """
        return self._client.put(
            self._client.api_host(),
            f"/v2/applications/{application_id}",
            params,
            auth_type=ApplicationV2.auth_type,
        )

    def delete_application(self, application_id):
        """
        Delete the application with `application_id`.
        """

        self._client.delete(
            self._client.api_host(),
            f"/v2/applications/{application_id}",
            auth_type=ApplicationV2.auth_type,
        )

    def list_applications(self, page_size=None, page=None):
        """
        List all applications for your account.

        Results are paged, so each page will need to be requested to see all applications.

        :param int page_size: The number of items in the page to be returned
        :param int page: The page number of the page to be returned.
        """
        params = _filter_none_values({"page_size": page_size, "page": page})

        return self._client.get(
            self._client.api_host(),
            "/v2/applications",
            params=params,
            auth_type=ApplicationV2.auth_type,
        )


class Application:
    auth_type = 'header'

    def __init__(self, client):
        self._client = client

    def create_application(self, application_data):
        """
        Create an application using the provided `application_data`.

        :param dict application_data: A JSON-style dict describing the application to be created.

        >>> client.application.create_application({ 'name': 'My Cool App!' })

        Details of the `application_data` dict are described at https://developer.vonage.com/api/application.v2#createApplication
        """
        return self._client.post(
            self._client.api_host(),
            "/v2/applications",
            application_data,
            auth_type=Application.auth_type,
        )

    def get_application(self, application_id):
        """
        Get application details for the application with `application_id`.

        The format of the returned dict is described at https://developer.vonage.com/api/application.v2#getApplication

        :param str application_id: The application ID.
        :rtype: dict
        """

        return self._client.get(
            self._client.api_host(),
            f"/v2/applications/{application_id}",
            auth_type=Application.auth_type,
        )

    def update_application(self, application_id, params):
        """
        Update the application with `application_id` using the values provided in `params`.


        """
        return self._client.put(
            self._client.api_host(),
            f"/v2/applications/{application_id}",
            params,
            auth_type=Application.auth_type,
        )

    def delete_application(self, application_id):
        """
        Delete the application with `application_id`.
        """

        self._client.delete(
            self._client.api_host(),
            f"/v2/applications/{application_id}",
            auth_type=Application.auth_type,
        )

    def list_applications(self, page_size=None, page=None):
        """
        List all applications for your account.

        Results are paged, so each page will need to be requested to see all applications.

        :param int page_size: The number of items in the page to be returned
        :param int page: The page number of the page to be returned.
        """
        params = _filter_none_values({"page_size": page_size, "page": page})

        return self._client.get(
            self._client.api_host(),
            "/v2/applications",
            params=params,
            auth_type=Application.auth_type,
        )


def _filter_none_values(d):
    return {k: v for k, v in d.items() if v is not None}
