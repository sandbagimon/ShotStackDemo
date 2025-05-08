import streamlit as st
import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
CONFIGURED_API_KEY = os.getenv("SHOTSTACK_API_KEY")
SHOTSTACK_TEMPLATE_ID_ENV = os.getenv("SHOTSTACK_TEMPLATE_ID", "2babe4ae-a4cf-4f49-a8c3-ccbdf2865f15")
SHOTSTACK_OWNER_ID_ENV = os.getenv("SHOTSTACK_OWNER_ID", "ttwxkrohlv")
SHOTSTACK_API_ENDPOINT = os.getenv("SHOTSTACK_API_ENDPOINT", "https://api.shotstack.io/edit/stage/templates/render")
SHOTSTACK_STATUS_ENDPOINT_TEMPLATE = os.getenv("SHOTSTACK_STATUS_ENDPOINT_TEMPLATE", "https://api.shotstack.io/edit/stage/render/{}")

# --- Default Merge Fields (With Updated Placeholders) ---
ORIGINAL_DEFAULT_MERGE_FIELDS = [
    {"find": "IMAGE_SRC",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/d41a22cf2369799b3edde708985e50131940373a342da7a122d0801eeb3936e0/image.jpg"},
    {"find": "IMAGE_SRC_2",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/cd50511e31af7da9cf991de96ef294fd2fc64f14a7d67ca1dbd701541d6973ad/image.jpg"},
    {"find": "IMAGE_SRC_3",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/067c4f6c74e9c0e3740cffb0d30d717108419f2a2cf8011a613808354c767b5a/image.jpg"},
    {"find": "IMAGE_SRC_4",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/96f370a3af180544087c634a431f652ba8f452f0b29d69ba4f9a1684a8871fc1/image.jpg"},
    {"find": "IMAGE_SRC_5",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/a8c253abd19c622b6ed15bcce357f70946dd9a98c56fc721664f1b610cf4e0f8/image.jpg"},
    {"find": "IMAGE_SRC_6",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/4e989518bb940cf2ecca14896ffd84e91a7ac8053e3dc21f98b9d78477b4f275/image.jpg"},
    {"find": "IMAGE_SRC_7",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/080956c133ab030da15d7a2c13de132a201568b9c026bf15f0af414d2aeadef5/image.jpg"},
    {"find": "IMAGE_SRC_8",
     "replace": "https://i2.au.reastatic.net/642x428-crop,format=webp/13903d93b2b87f53177af5c4dac37e547c36ec4fec3996db3633658d8fbbb1a3/image.jpg"},
    {"find": "PRODUCT_NAME", "replace": "PRODUCT NAME"},
    {"find": "BRAND_NAME", "replace": "BRAND NAME"},
    {"find": "PRODUCT_CTA", "replace": "FREE DELIVERY"},
    {"find": "PRODUCT_TEXT", "replace": "YOUR TEXT GOES HERE"},
    {"find": "LOGO_SRC",
     "replace": "https://templates.shotstack.io/holiday-season-glam-template/68d19af4-20b9-41af-a999-1b3838a8bd6d/source.png"},
    {"find": "PRODUCT_SUBTITLE", "replace": "YOUR SUBTITLE GOES HERE"}
]

# --- Helper Functions ---
def get_original_placeholder(field_key_to_find):
    """Gets the original placeholder value for a given field key."""
    for item in ORIGINAL_DEFAULT_MERGE_FIELDS:
        if item["find"] == field_key_to_find:
            return item["replace"]
    return ""

# --- Shotstack API Call Functions ---
def render_video_with_shotstack(api_key_to_use, template_id, merge_fields, owner_id):
    """Submits a render request to the Shotstack API."""
    if not api_key_to_use:
        st.error("API Key is not configured. Please ensure SHOTSTACK_API_KEY is set in your .env file.")
        return None
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key_to_use
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

def get_render_status(api_key_to_use, render_id):
    """Gets the render status for a given render ID."""
    if not api_key_to_use:
        st.error("API Key is not configured. Please ensure SHOTSTACK_API_KEY is set in your .env file.")
        return None
    if not render_id:
        return None
    headers = {
        "x-api-key": api_key_to_use,
        "Accept": "application/json"
    }
    status_url = SHOTSTACK_STATUS_ENDPOINT_TEMPLATE.format(render_id)
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

# Initialize session state for form fields using ORIGINAL_DEFAULT_MERGE_FIELDS placeholders
for field_data in ORIGINAL_DEFAULT_MERGE_FIELDS:
    session_key = f"user_input_{field_data['find']}"
    if session_key not in st.session_state:
        st.session_state[session_key] = field_data["replace"]

# Initialize other session state variables
if 'template_id' not in st.session_state:
    st.session_state.template_id = SHOTSTACK_TEMPLATE_ID_ENV
if 'owner_id' not in st.session_state:
    st.session_state.owner_id = SHOTSTACK_OWNER_ID_ENV
if 'render_id' not in st.session_state:
    st.session_state.render_id = None
if 'video_url' not in st.session_state:
    st.session_state.video_url = None
if 'last_status' not in st.session_state:
    st.session_state.last_status = None

# --- Sidebar ---
st.sidebar.header("API Configuration (Stage)")
st.session_state.template_id = st.sidebar.text_input("Shotstack Template ID (Stage)",
                                                     value=st.session_state.template_id)
st.session_state.owner_id = st.sidebar.text_input("Shotstack Owner ID", value=st.session_state.owner_id)

# --- Main Page Content ---
if not CONFIGURED_API_KEY:
    st.error("CRITICAL: Shotstack API Key is not configured. Please set SHOTSTACK_API_KEY in your .env file.")
    st.stop()

st.markdown(f"Using STAGE environment | Template ID: `{st.session_state.template_id}` | Owner ID: `{st.session_state.owner_id}`")
st.markdown(f"Render Submission Endpoint: `{SHOTSTACK_API_ENDPOINT}`")
st.markdown(f"Status Query Endpoint Template: `{SHOTSTACK_STATUS_ENDPOINT_TEMPLATE.format('{renderId}')}`")

# --- Form Section (Visible if not rendering or render finished/failed) ---
if not st.session_state.render_id or st.session_state.last_status in ["done", "failed"]:
    st.header("🎨 Customize Video Content")
    st.markdown("Modify the text and image links here, then click 'Generate Video'.")

    with st.form(key="video_customization_form"):
        user_inputs_from_form = {}
        cols_per_row = 2
        col1, col2 = st.columns(cols_per_row)

        for i, field_data in enumerate(ORIGINAL_DEFAULT_MERGE_FIELDS):
            field_key = field_data["find"]
            session_key_for_display = f"user_input_{field_key}"

            current_col = col1 if i % cols_per_row == 0 else col2
            label_prefix = "🔗" if "IMAGE_SRC" in field_key or "LOGO_SRC" in field_key else "📝"
            label = f"{label_prefix} {field_key.replace('_', ' ').title()}"

            user_inputs_from_form[field_key] = current_col.text_input(
                label,
                value=st.session_state[session_key_for_display],
                key=f"input_form_{field_key}"
            )
        submit_button = st.form_submit_button(label="🚀 Generate Video (Stage)")

    if submit_button:
        # Update session_state with the values manually entered in the form
        for field_key, input_value in user_inputs_from_form.items():
            st.session_state[f"user_input_{field_key}"] = input_value

        # Reset render status variables
        st.session_state.render_id = None
        st.session_state.video_url = None
        st.session_state.last_status = None

        # Validation
        if not st.session_state.template_id:
            st.error("Please enter a valid STAGE Template ID (check sidebar or .env file)!")
        elif not st.session_state.owner_id:
            st.error("Please enter a valid Shotstack Owner ID (check sidebar or .env file)!")
        else:
            st.info("Preparing request data (Stage)...")
            current_merge_fields = []
            # Prepare merge fields using the latest values from session_state
            for field_data in ORIGINAL_DEFAULT_MERGE_FIELDS:
                find_key = field_data["find"]
                current_merge_fields.append({
                    "find": find_key,
                    "replace": st.session_state[f"user_input_{find_key}"]
                })

            with st.spinner("Calling Shotstack STAGE API to submit render job..."):
                api_response = render_video_with_shotstack(
                    CONFIGURED_API_KEY,
                    st.session_state.template_id,
                    current_merge_fields,
                    st.session_state.owner_id
                )

            if api_response:
                if api_response.get("success"):
                    render_id_from_api = api_response.get("response", {}).get("id")
                    message = api_response.get("response", {}).get("message")
                    st.session_state.render_id = render_id_from_api
                    st.session_state.last_status = "submitted"
                    st.success(f"✅ (Stage) Video render job submitted! Status: {message}, Render ID: {st.session_state.render_id}")
                    st.info("Checking render progress...")
                    st.rerun()
                else:
                    st.error(f"(Stage) API submission failed: {api_response.get('message', 'Unknown error')}")
                    st.json(api_response)

# --- Status Checking Section (Visible if rendering is in progress) ---
if st.session_state.render_id and st.session_state.last_status not in ["done", "failed"]:
    st.header("⏳ (Stage) Video Rendering Progress")
    st.write(f"Processing Render ID: `{st.session_state.render_id}`")
    status_placeholder = st.empty()

    with st.spinner("Fetching latest render status (Stage)..."):
        status_response = get_render_status(CONFIGURED_API_KEY, st.session_state.render_id)

    if status_response:
        if status_response.get("success"):
            render_data = status_response.get("response", {})
            current_status = render_data.get("status")
            st.session_state.last_status = current_status
            status_placeholder.info(f"Current Status (Stage): **{current_status.upper()}**")

            if current_status == "done":
                video_url = render_data.get("url")
                st.session_state.video_url = video_url
                status_placeholder.success("🎉 (Stage) Video rendering complete!")

                # --- VIDEO DISPLAY WITH HTML/CSS FOR SCALING ---
                vid_col, _ = st.columns([2, 1]) # Keep using columns for layout width control
                with vid_col:
                    # Use st.markdown with HTML video tag and CSS for responsive scaling
                    video_html = f"""
                        <video controls style="max-width: 100%; height: auto;">
                            <source src="{st.session_state.video_url}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        """
                    st.markdown(video_html, unsafe_allow_html=True)
                # --- END VIDEO DISPLAY ---

                if st.button("✨ Start New Video Edit (Stage)"):
                    st.session_state.render_id = None
                    st.session_state.video_url = None
                    st.session_state.last_status = None
                    # Reset form fields to original placeholders
                    for field_data_orig in ORIGINAL_DEFAULT_MERGE_FIELDS:
                        st.session_state[f"user_input_{field_data_orig['find']}"] = field_data_orig["replace"]
                    st.rerun()

            elif current_status == "failed":
                error_message = render_data.get("error", "Unknown error")
                status_placeholder.error(f"☠️ (Stage) Video rendering failed. Reason: {error_message}")
                st.json(render_data)
                if st.button("Try Editing Again (Stage)"):
                    st.session_state.render_id = None
                    st.session_state.video_url = None
                    st.session_state.last_status = None
                    st.rerun()
            else:
                status_placeholder.info(
                    f"(Stage) Video is still processing, status: **{current_status.upper()}**. The page will refresh automatically in a few seconds.")
                time.sleep(10)
                st.rerun()
        else:
            st.error(f"When fetching status (Stage), API returned a business error: {status_response.get('message', 'Unknown business error')}")
            st.json(status_response)
            if st.button("Refresh Status Manually (Stage)"):
                st.rerun()

# --- Completed Video Display Section ---
elif st.session_state.video_url and st.session_state.last_status == "done":
    st.header("✅ (Stage) Completed Video")
    # --- VIDEO DISPLAY WITH HTML/CSS FOR SCALING ---
    vid_col, _ = st.columns([2, 1]) # Keep using columns for layout width control
    with vid_col:
        # Use st.markdown with HTML video tag and CSS for responsive scaling
        video_html = f"""
            <video controls style="max-width: 100%; height: auto;">
                <source src="{st.session_state.video_url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            """
        st.markdown(video_html, unsafe_allow_html=True)
    # --- END VIDEO DISPLAY ---

    if st.button("✨ Start New Video Edit (Stage)"):
        st.session_state.render_id = None
        st.session_state.video_url = None
        st.session_state.last_status = None
        # Reset form fields to original placeholders
        for field_data_orig in ORIGINAL_DEFAULT_MERGE_FIELDS:
            st.session_state[f"user_input_{field_data_orig['find']}"] = field_data_orig["replace"]
        st.rerun()

# --- Failed Render Display Section ---
elif st.session_state.last_status == "failed":
    st.error("The previous (Stage) video rendering failed.")
    if st.button("Try Editing Again (Stage)"):
        st.session_state.render_id = None
        st.session_state.video_url = None
        st.session_state.last_status = None
        st.rerun()

# --- Footer ---
st.markdown("---")
st.caption("Shotstack Streamlit Video Editor (Stage Environment)")