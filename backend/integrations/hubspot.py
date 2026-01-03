# hubspot.py
"""
HubSpot OAuth and data integration.

This module implements:
1. OAuth 2.0 authorization flow for HubSpot
2. Secure state handling using Redis
3. One-time credential retrieval
4. Fetching CRM objects (Companies and Contacts) from HubSpot APIs

Implementation closely follows existing Airtable/Notion integration patterns
for consistency across integrations.
"""
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import json
import secrets
import base64
import httpx
import asyncio
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis
import requests
from integrations.integration_item import IntegrationItem

CLIENT_ID = "875c8cab-c41a-420c-8535-072f75c9d886"
CLIENT_SECRET = "dc748a9e-023f-4bdd-9a6c-c5b8d3b61100"
REDIRECT_URI = "http://localhost:8000/integrations/hubspot/oauth2callback"
AUTHORIZATION_URL = "https://app.hubspot.com/oauth/authorize"
TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"

SCOPES = "crm.objects.companies.read crm.objects.contacts.read"


# Step 1: Initiates HubSpot OAuth flow
# - Generates a cryptographically secure state
# - Persists state in Redis for CSRF protection
# - Returns the HubSpot authorization URL to the frontend
async def authorize_hubspot(user_id, org_id):
    state_data = {
        "state": secrets.token_urlsafe(32),
        "user_id": user_id,
        "org_id": org_id,
    }
    encoded_state = base64.urlsafe_b64encode(
        json.dumps(state_data).encode("utf-8")
    ).decode("utf-8")
    auth_url = (
        f"{AUTHORIZATION_URL}"
        f"?client_id={CLIENT_ID}"
        f"&scope={SCOPES}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={encoded_state}"
        f"&response_type=code"
    )
    await add_key_value_redis(
        f"hubspot_state:{org_id}:{user_id}", json.dumps(state_data), expire=600
    )
    return auth_url


# Step 2: OAuth callback handler
# - Validates OAuth state to prevent CSRF attacks
# - Exchanges authorization code for access token
# - Stores credentials temporarily in Redis
# - Closes OAuth popup window after completion
async def oauth2callback_hubspot(request: Request):
    if request.query_params.get("error"):
        raise HTTPException(
            status_code=400, detail=request.query_params.get("error_description")
        )
    code = request.query_params.get("code")
    encoded_state = request.query_params.get("state")
    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode("utf-8"))
    original_state = state_data.get("state")
    user_id = state_data.get("user_id")
    org_id = state_data.get("org_id")

    # Validate stored state against callback state to prevent replay/CSRF attacks
    saved_state = await get_value_redis(f"hubspot_state:{org_id}:{user_id}")
    if not saved_state or original_state != json.loads(saved_state).get("state"):
        raise HTTPException(status_code=400, detail="State does not match.")
    # Exchange authorization code for access token using HubSpot OAuth token endpoint
    # Client credentials are sent in the request body as required by HubSpot

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ),
            delete_key_redis(f"hubspot_state:{org_id}:{user_id}"),
        )
        await add_key_value_redis(
            f"hubspot_credentials:{org_id}:{user_id}",
            json.dumps(response.json()),
            expire=600,
        )
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


# Step 3: Returns OAuth credentials to frontend
# - Credentials are read once and immediately deleted
# - Prevents accidental reuse or long-lived token storage
async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f"hubspot_credentials:{org_id}:{user_id}")
    if not credentials:
        raise HTTPException(status_code=400, detail="No credentials found.")
    credentials = json.loads(credentials)
    await delete_key_redis(f"hubspot_credentials:{org_id}:{user_id}")

    return credentials


def _create_integration_item_metadata_object(response_json) -> IntegrationItem:
    return IntegrationItem(
        id=response_json.get("id"),
        name=response_json.get("name"),
        type=response_json.get("type"),
    )


# Step 4: Fetch HubSpot CRM objects using OAuth access token
# - Retrieves Companies and Contacts
# - Maps API responses to IntegrationItem objects
# - Printing results is intentional as suggested by assessment instructions
async def get_items_hubspot(credentials):
    credentials = json.loads(credentials)

    access_token = credentials.get("access_token")
    url = "https://api.hubapi.com/crm/v3/objects/companies"

    list_of_integration_item_metadata = []
    list_of_companies = []
    list_of_contacts = []
    _fetch_items(access_token, url, list_of_companies, "Company")
    if list_of_companies:
        for response in list_of_companies:
            list_of_integration_item_metadata.append(
                _create_integration_item_metadata_object(response)
            )
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    _fetch_items(access_token, url, list_of_contacts, "Contact")
    if list_of_contacts:
        for response in list_of_contacts:
            list_of_integration_item_metadata.append(
                _create_integration_item_metadata_object(response)
            )
    print(f"list_of_integration_item_metadata: {list_of_integration_item_metadata}")

    return list_of_integration_item_metadata


# Helper function to fetch CRM objects from HubSpot
# - Uses Bearer token authentication
# - Normalizes response into a simple structure
# - Keeps logic shared for companies and contacts
def _fetch_items(
    access_token: str, url: str, aggregated_response: list, type: str
) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=response.text)
    data = response.json()
    results = data.get("results", [])
    for result in results:
        aggregated_response.append(
            {
                "id": result.get("id"),
                "name": result.get("properties", {}).get("name"),
                "type": type,
            }
        )

    return aggregated_response
