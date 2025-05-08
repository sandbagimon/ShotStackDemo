import streamlit as st
import requests
import json
import time

# --- Configuration ---
SHOTSTACK_API_KEY = "P61e1j953LJEz9hLQDjAMBzxBZid0ffjZul7BFml" # Replace with your actual Stage API key
SHOTSTACK_API_ENDPOINT = "https://api.shotstack.io/edit/stage/templates/render"
# Update to the correct STAGE status endpoint template, based on your cURL example
SHOTSTACK_STATUS_ENDPOINT_TEMPLATE = "https://api.shotstack.io/edit/stage/render/{}"
TEMPLATE_ID = "2babe4ae-a4cf-4f49-a8c3-ccbdf2865f15" # Replace with your actual Template ID
SHOTSTACK_OWNER_ID = "ttwxkrohlv" # Replace with your actual Owner ID

DEFAULT_MERGE_FIELDS = [
    {"find": "IMAGE_SRC",
     "replace": "https://shotstack-ingest-api-v1-renditions.s3.ap-southeast-2.amazonaws.com/jhq060blqb/zzz01jtm-dns01-k367s-7z52d-8ax37p/shotstack-proxy.webp"},
    {"find": "IMAGE_SRC_2",
     "replace": "https://shotstack-ingest-api-v1-renditions.s3.ap-southeast-2.amazonaws.com/jhq060blqb/zzz01jtm-dnhv4-5hsad-h8td3-w684vj/shotstack-proxy.webp"},
    {"find": "IMAGE_SRC_3",
     "replace": "https://shotstack-ingest-api-v1-renditions.s3.ap-southeast-2.amazonaws.com/jhq060blqb/zzz01jtm-dn89q-kjz33-faqxj-m2hz0w/shotstack-proxy.webp"},
    {"find": "IMAGE_SRC_4",
     "replace": "https://templates.shotstack.io/holiday-season-glam-template/c9d09c62-9ef0-480e-b87f-fffe6702eb70/source.jpg"},
    {"find": "IMAGE_SRC_5",
     "replace": "https://templates.shotstack.io/holiday-season-glam-template/81012371-9be6-4b0a-9b01-21acd8618871/source.jpg"},
    {"find": "IMAGE_SRC_6",
     "replace": "https://templates.shotstack.io/holiday-season-glam-template/c011e0a8-720d-4c60-a330-7a4e7ac1769a/source.jpg"},
    {"find": "IMAGE_SRC_7",
     "replace": "https://templates.shotstack.io/holiday-season-glam-template/372c1fa9-a16a-4220-95b6-d247ea0910f0/source.jpg"},
    {"find": "IMAGE_SRC_8",
     "replace": "https://templates.shotstack.io/holiday-season-glam-template/ed781b38-f9da-400e-ad63-1508781f0a8a/source.jpg"},
    {"find": "PRODUCT_NAME", "replace": "PRODUCT NAME"},
    {"find": "BRAND_NAME", "replace": "BRAND NAME"},
    {"find": "PRODUCT_CTA", "replace": "FREE DELIVERY"},
    {"find": "PRODUCT_TEXT", "replace": "YOUR TEXT GOES HERE"},
    {"find": "LOGO_SRC",
     "replace": "https://templates.shotstack.io/holiday-season-glam-template/68d19af4-20b9-41af-a999-1b3838a8bd6d/source.png"},
    {"find": "PRODUCT_SUBTITLE", "replace": "YOUR SUBTITLE GOES HERE"}
]


# --- Shotstack API Call Functions ---
def render_video_with_shotstack(api_key, template_id, merge_fields, owner_id):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "id": template_id,
        "merge": merge_fields,
        "owner": owner_id
    }
    try:
        response = requests.post(SHOTSTACK_API_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed (render_video): {e}")
        try:
            st.error(f"API response content: {response.text}")
        except:
            pass
        return None


def get_render_status(api_key, render_id):
    """
    Get the render status for the specified render_id.
    """
    if not render_id:
        return None

    headers = {
        "x-api-key": api_key,
        "Accept": "application/json"  # Add Accept header, based on cURL example
    }
    status_url = SHOTSTACK_STATUS_ENDPOINT_TEMPLATE.format(render_id)  # Format URL using render_id
    try:
        response = requests.get(status_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get render status: {e}")
        try:
            st.error(f"API response content: {response.text}")
        except:
            pass
        return None


# --- Streamlit App Interface ---
st.set_page_config(page_title="Shotstack Video Editor (Stage)", layout="wide")
st.title("🎬 Shotstack Video Customization Tool (Stage)")

if 'api_key' not in st.session_state:
    st.session_state.api_key = SHOTSTACK_API_KEY
if 'template_id' not in st.session_state:
    st.session_state.template_id = TEMPLATE_ID
if 'owner_id' not in st.session_state:
    st.session_state.owner_id = SHOTSTACK_OWNER_ID
if 'render_id' not in st.session_state:
    st.session_state.render_id = None
if 'video_url' not in st.session_state:
    st.session_state.video_url = None
if 'last_status' not in st.session_state:
    st.session_state.last_status = None

st.sidebar.header("API Configuration (Stage)")
st.session_state.api_key = st.sidebar.text_input("Shotstack API Key (Stage)", value=st.session_state.api_key,
                                                 type="password")
st.session_state.template_id = st.sidebar.text_input("Shotstack Template ID (Stage)",
                                                     value=st.session_state.template_id)
st.session_state.owner_id = st.sidebar.text_input("Shotstack Owner ID", value=st.session_state.owner_id)

st.markdown(f"Using STAGE environment | Template ID: `{st.session_state.template_id}` | Owner ID: `{st.session_state.owner_id}`")
st.markdown(f"Render Submission Endpoint: `{SHOTSTACK_API_ENDPOINT}`")
st.markdown(f"Status Query Endpoint Template: `{SHOTSTACK_STATUS_ENDPOINT_TEMPLATE.format('{renderId}')}`")

if not st.session_state.render_id or st.session_state.last_status in ["done", "failed"]:
    st.header("🎨 Customize Video Content")
    st.markdown("Modify the text and image links here, then click the 'Generate Video' button.")

    with st.form(key="video_customization_form"):
        user_inputs = {}
        cols_per_row = 2
        col1, col2 = st.columns(cols_per_row)

        for i, field_data in enumerate(DEFAULT_MERGE_FIELDS):
            field_key = field_data["find"]
            session_key = f"user_input_{field_key}"
            if session_key not in st.session_state:
                st.session_state[session_key] = field_data["replace"]

            current_col = col1 if i % cols_per_row == 0 else col2
            label_prefix = "🔗" if "IMAGE_SRC" in field_key or "LOGO_SRC" in field_key else "📝"
            label = f"{label_prefix} {field_key.replace('_', ' ').title()}"

            user_inputs[field_key] = current_col.text_input(
                label,
                value=st.session_state[session_key],
                key=f"input_{field_key}"
            )
        submit_button = st.form_submit_button(label="🚀 Generate Video (Stage)")

    if submit_button:
        for field_key, input_value in user_inputs.items():
            st.session_state[f"user_input_{field_key}"] = input_value

        st.session_state.render_id = None
        st.session_state.video_url = None
        st.session_state.last_status = None

        if not st.session_state.api_key:
            st.error("Please enter a valid STAGE API Key!")
        elif not st.session_state.template_id:
            st.error("Please enter a valid STAGE Template ID!")
        elif not st.session_state.owner_id:
            st.error("Please enter a valid Shotstack Owner ID!")
        else:
            st.info("Preparing request data (Stage)...")
            current_merge_fields = []
            for field_data in DEFAULT_MERGE_FIELDS:
                find_key = field_data["find"]
                current_merge_fields.append({
                    "find": find_key,
                    "replace": user_inputs[find_key]
                })

            with st.spinner("Calling Shotstack STAGE API to submit render job..."):
                api_response = render_video_with_shotstack(
                    st.session_state.api_key,
                    st.session_state.template_id,
                    current_merge_fields,
                    st.session_state.owner_id
                )

            if api_response:
                if api_response.get("success"):
                    render_id_from_api = api_response.get("response", {}).get("id")
                    message = api_response.get("response", {}).get("message")
                    st.session_state.render_id = render_id_from_api
                    st.session_state.last_status = "submitted"  # Or could be 'queued'
                    st.success(f"✅ (Stage) Video render job submitted! Status: {message}, Render ID: {st.session_state.render_id}")
                    st.info("Checking render progress...")
                    st.rerun()
                else:
                    st.error(f"(Stage) API submission failed: {api_response.get('message', 'Unknown error')}")
                    st.json(api_response)  # Display specific error response
            else:
                st.error("(Stage) API request could not be submitted successfully.")

if st.session_state.render_id and st.session_state.last_status not in ["done", "failed"]:
    st.header("⏳ (Stage) Video Rendering Progress")
    st.write(f"Processing Render ID: `{st.session_state.render_id}`")

    status_placeholder = st.empty()
    video_placeholder = st.empty()

    with st.spinner("Fetching latest render status (Stage)..."):
        status_response = get_render_status(st.session_state.api_key, st.session_state.render_id)

    if status_response:  # Check if status_response is None
        if status_response.get("success"):  # API call successful and business success
            render_data = status_response.get("response", {})
            current_status = render_data.get("status")
            st.session_state.last_status = current_status

            status_placeholder.info(f"Current Status (Stage): **{current_status.upper()}**")

            if current_status == "done":
                video_url = render_data.get("url")
                st.session_state.video_url = video_url
                status_placeholder.success("🎉 (Stage) Video rendering complete!")
                video_placeholder.video(st.session_state.video_url)
                if st.button("✨ Start New Video Edit (Stage)"):
                    st.session_state.render_id = None
                    st.session_state.video_url = None
                    st.session_state.last_status = None
                    st.rerun()
            elif current_status == "failed":
                error_message = render_data.get("error", "Unknown error")
                details = render_data.get("errors", "No details")  # Some APIs might use 'details' or other fields
                status_placeholder.error(f"☠️ (Stage) Video rendering failed. Reason: {error_message}")
                st.json(render_data)  # Display full failure response data
                if st.button("Try Editing Again (Stage)"):
                    st.session_state.render_id = None
                    st.session_state.video_url = None
                    st.session_state.last_status = None
                    st.rerun()
            else:
                status_placeholder.info(
                    f"(Stage) Video is still processing, status: **{current_status.upper()}**. The page will refresh automatically in a few seconds.")
                time.sleep(10) # Keep the delay
                st.rerun()
        else:  # API call successful but business failure (e.g., success: false in response)
            st.error(f"When fetching status (Stage), API returned a business error: {status_response.get('message', 'Unknown business error')}")
            st.json(status_response)  # Display full error response
            if st.button("Refresh Status Manually (Stage)"):
                st.rerun()
    else:  # status_response is None, meaning get_render_status had a request exception
        st.warning("Could not get render status (Stage). Please check your network or API Key, and review the error logs above.")
        if st.button("Refresh Status Manually (Stage)"):
            st.rerun()


elif st.session_state.video_url and st.session_state.last_status == "done":
    st.header("✅ (Stage) Completed Video")
    st.video(st.session_state.video_url)
    if st.button("✨ Start New Video Edit (Stage)"):
        st.session_state.render_id = None
        st.session_state.video_url = None
        st.session_state.last_status = None
        st.rerun()

elif st.session_state.last_status == "failed":
    st.error("The previous (Stage) video rendering failed.")
    if st.button("Try Editing Again (Stage)"):
        st.session_state.render_id = None
        st.session_state.video_url = None
        st.session_state.last_status = None
        st.rerun()

st.markdown("---")
st.caption("Shotstack Streamlit Video Editor (Stage Environment)")