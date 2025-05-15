import streamlit as st
import requests
import json
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI  # OpenAI Import
from supabase import create_client, Client  # Supabase Import
import mimetypes  # For guessing content type

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
CONFIGURED_API_KEY = os.getenv("SHOTSTACK_API_KEY")
SHOTSTACK_TEMPLATE_ID_ENV = os.getenv("SHOTSTACK_TEMPLATE_ID", "2babe4ae-a4cf-4f49-a8c3-ccbdf2865f15")
SHOTSTACK_OWNER_ID_ENV = os.getenv("SHOTSTACK_OWNER_ID", "ttwxkrohlv")
SHOTSTACK_API_ENDPOINT = os.getenv("SHOTSTACK_API_ENDPOINT", "https://api.shotstack.io/edit/stage/templates/render")
SHOTSTACK_STATUS_ENDPOINT_TEMPLATE = os.getenv("SHOTSTACK_STATUS_ENDPOINT_TEMPLATE",
                                               "https://api.shotstack.io/edit/stage/render/{}")

GEMINI_API_KEY_ENV = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY_ENV = os.getenv("OPENAI_API_KEY")  # OpenAI API Key

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Using Service Key for backend operations
SUPABASE_BUCKET_NAME = "videobgm"

TARGET_VIDEO_DURATION_SECONDS = int(os.getenv("TARGET_VIDEO_DURATION_SECONDS", "30"))
WORDS_PER_SECOND_ESTIMATE = float(os.getenv("WORDS_PER_SECOND_ESTIMATE", "2.5"))

# OpenAI TTS Configuration
DEFAULT_OPENAI_TTS_VOICE = "alloy"
DEFAULT_OPENAI_TTS_MODEL = "gpt-4o-mini-tts"

TEMP_AUDIO_FILENAME = "temp_narration_openai.mp3"

# --- Default Merge Fields ---
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
    {"find": "PRODUCT_SUBTITLE", "replace": "YOUR SUBTITLE GOES HERE"},
    {"find": "NARRATION_AUDIO_SRC", "replace": ""}
]


# --- Helper Functions ---
def get_original_placeholder(field_key_to_find):
    for item in ORIGINAL_DEFAULT_MERGE_FIELDS:
        if item["find"] == field_key_to_find:
            return item["replace"]
    return ""


# --- LLM and TTS Functions ---
def generate_script_with_gemini(api_key, description, target_duration_seconds, words_per_second,
                                model_name="gemini-2.5-pro-preview-05-06"):
    if not api_key:
        st.error("Gemini API Key is missing. Please configure it in your .env file.")
        return "Error: Gemini API Key not configured."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        target_word_count = int(target_duration_seconds * words_per_second)
        prompt = (
            f"You are an enthusiastic and persuasive real estate sales agent creating a promotional video script aimed at attracting potential residents. "
            f"Your task is to transform the following property description into a compelling and inviting narration. "
            f"The script should be approximately {target_word_count} words long, suitable for a {target_duration_seconds}-second video, and delivered in a warm, confident, and professional sales tone. "
            f"Highlight the key benefits and lifestyle a resident would enjoy. Make them feel like this is their next dream home. "
            f"Focus on the most appealing features that would matter to someone looking to live there. "
            f"Keep the language clear, aspirational, and avoid overly technical jargon. "
            f"Conclude with an inviting remark or a subtle call to imagine themselves living there. "
            f"Strictly provide ONLY the spoken narration script, with no scene directions, camera instructions, or any other text.\n\n"
            f"Property Description:\n\"\"\"\n{description}\n\"\"\"\n\n"
            f"Generate ONLY the narration script text, nothing else."
        )
        with st.spinner(f"🤖 Generating script with Gemini (target: ~{target_word_count} words)..."):
            response = model.generate_content(prompt)

        generated_text = ""
        if hasattr(response, 'parts') and response.parts:
            generated_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
        elif hasattr(response, 'text'):
            generated_text = response.text

        if not generated_text:
            feedback = "No prompt feedback available."
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                feedback = str(response.prompt_feedback)
            st.error(f"Gemini returned an empty script. Feedback: {feedback}")
            return "Error: Gemini returned an empty script."
        return generated_text.strip()
    except Exception as e:
        st.error(f"Error generating script with Gemini: {e}")
        if hasattr(e, 'response'): st.json(e.response.json() if hasattr(e.response, 'json') else str(e.response))
        return f"Error during Gemini API call: {str(e)}"


def generate_openai_tts_audio_to_file(api_key, script_text, output_filepath, voice_model, tts_model):
    """Generates TTS audio using OpenAI Speech API and saves it to a local file."""
    if not api_key:
        st.error("OpenAI API Key is missing. Please configure it in your .env file.")
        return None
    try:
        client = OpenAI(api_key=api_key)
        st.info(f"Synthesizing speech with OpenAI TTS (voice: {voice_model}, model: {tts_model})...")

        with client.audio.speech.with_streaming_response.create(
                model=tts_model,
                voice=voice_model,
                input=script_text,
                response_format="mp3"
        ) as response:
            response.stream_to_file(output_filepath)

        st.success(f'OpenAI TTS audio content written to local file: "{output_filepath}"')
        return output_filepath
    except Exception as e:
        st.error(f"OpenAI TTS API error: {e}")
        return None


def upload_audio_and_get_public_url(local_filepath, filename_in_bucket):
    """
    Uploads the local audio file to Supabase Storage and returns its public URL.
    Shotstack needs a publicly accessible URL for the audio.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase URL or Key is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env.")
        return None

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        content_type, _ = mimetypes.guess_type(local_filepath)
        if not content_type:
            content_type = "audio/mpeg"

        with open(local_filepath, 'rb') as f:
            st.info(
                f"Uploading '{local_filepath}' to Supabase bucket '{SUPABASE_BUCKET_NAME}' as '{filename_in_bucket}'...")
            upload_response = supabase.storage.from_(SUPABASE_BUCKET_NAME).upload(
                path=filename_in_bucket,
                file=f,
                file_options={"content-type": content_type, "upsert": "false"}
            )

        public_url_data = supabase.storage.from_(SUPABASE_BUCKET_NAME).get_public_url(filename_in_bucket)

        if isinstance(public_url_data, str):
            st.success(f"Successfully uploaded to Supabase. Public URL: {public_url_data}")
            return public_url_data
        else:
            st.error(f"Failed to get public URL from Supabase. Response: {public_url_data}")
            return None

    except Exception as e:
        st.error(f"Supabase upload or URL retrieval failed: {e}")
        if hasattr(e, 'message') and isinstance(e.message, dict) and 'message' in e.message:
            st.error(f"Supabase specific error: {e.message['message']}")
        elif hasattr(e, 'args') and e.args:
            st.error(f"Error details: {e.args[0]}")
        return None


def generate_narration_audio_url(openai_api_key, script_text, openai_tts_voice, openai_tts_model):
    """Orchestrates TTS generation with OpenAI, saving to file, uploading, and getting public URL."""
    if not script_text or "Error:" in script_text:
        st.warning("Skipping OpenAI TTS due to script generation error or empty script.")
        return None

    local_audio_file = TEMP_AUDIO_FILENAME
    public_audio_url = None

    try:
        with st.spinner(
                f"Generating narration with OpenAI TTS (Voice: {openai_tts_voice}, Model: {openai_tts_model})..."):
            if not generate_openai_tts_audio_to_file(openai_api_key, script_text, local_audio_file, openai_tts_voice,
                                                     openai_tts_model):
                st.error("OpenAI TTS failed to generate local audio file.")
                return None

        with st.spinner(f"Uploading narration audio to Supabase ({SUPABASE_BUCKET_NAME})..."):
            timestamp = int(time.time())
            base_name = os.path.basename(local_audio_file).replace(" ", "_")
            unique_filename_in_bucket = f"narration_openai_{timestamp}_{base_name}"

            public_audio_url = upload_audio_and_get_public_url(local_audio_file, unique_filename_in_bucket)

        if public_audio_url:
            st.success(f"🎙️ OpenAI TTS audio processed. Public URL (Supabase): {public_audio_url}")
        else:
            st.error("Failed to upload audio to Supabase or get public URL.")

        return public_audio_url

    except Exception as e:
        st.error(f"Error in OpenAI TTS audio processing pipeline: {e}")
        return None
    finally:
        if os.path.exists(local_audio_file):
            try:
                os.remove(local_audio_file)
                st.info(f"Temporary local audio file '{local_audio_file}' removed.")
            except Exception as e_rem:
                st.warning(f"Could not remove temporary audio file {local_audio_file}: {e_rem}")


# --- Shotstack API Call Functions (unchanged) ---
def render_video_with_shotstack(api_key_to_use, template_id, merge_fields, owner_id):
    if not api_key_to_use:
        st.error("Shotstack API Key is not configured.")
        return None
    headers = {"Content-Type": "application/json", "x-api-key": api_key_to_use}
    payload = {"id": template_id, "merge": merge_fields, "owner": owner_id}
    try:
        st.info("Sending request to Shotstack API...")
        response = requests.post(SHOTSTACK_API_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed (render_video): {e}")
        if hasattr(e, 'response') and e.response is not None: st.error(f"API response content: {e.response.text}")
        return None


def get_render_status(api_key_to_use, render_id):
    if not api_key_to_use:
        st.error("Shotstack API Key is not configured.")
        return None
    if not render_id: return None
    headers = {"x-api-key": api_key_to_use, "Accept": "application/json"}
    status_url = SHOTSTACK_STATUS_ENDPOINT_TEMPLATE.format(render_id)
    try:
        response = requests.get(status_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get render status: {e}")
        if hasattr(e, 'response') and e.response is not None: st.error(f"API response content: {e.response.text}")
        return None


# --- Streamlit App Interface ---
st.set_page_config(page_title="AI Video Editor (OpenAI TTS + Supabase)", layout="wide")
st.title("🎬 AI Video Customization Tool (Gemini & OpenAI TTS & Supabase)")

# Initialize session state
for field_data in ORIGINAL_DEFAULT_MERGE_FIELDS:
    session_key = f"user_input_{field_data['find']}"
    if session_key not in st.session_state:
        st.session_state[session_key] = "" if field_data['find'] == "NARRATION_AUDIO_SRC" else field_data["replace"]

default_desc = "Spacious 3-bedroom apartment with stunning city views, modern kitchen, and a large balcony. Located in a prime downtown area, close to parks and amenities. Features hardwood floors, en-suite master bathroom, and ample storage space. Perfect for families or professionals seeking a vibrant urban lifestyle."
if 'property_description' not in st.session_state: st.session_state.property_description = default_desc
if 'generated_script' not in st.session_state: st.session_state.generated_script = None
if 'tts_audio_url' not in st.session_state: st.session_state.tts_audio_url = None
if 'template_id' not in st.session_state: st.session_state.template_id = SHOTSTACK_TEMPLATE_ID_ENV
if 'owner_id' not in st.session_state: st.session_state.owner_id = SHOTSTACK_OWNER_ID_ENV
if 'render_id' not in st.session_state: st.session_state.render_id = None
if 'video_url' not in st.session_state: st.session_state.video_url = None
if 'last_status' not in st.session_state: st.session_state.last_status = None
# API keys are now sourced directly from ENV VARS, not session state for override
# if 'current_gemini_api_key' not in st.session_state: st.session_state.current_gemini_api_key = GEMINI_API_KEY_ENV
# if 'current_openai_api_key' not in st.session_state: st.session_state.current_openai_api_key = OPENAI_API_KEY_ENV

# --- Sidebar ---
st.sidebar.header("API Configuration (Stage)")
st.session_state.template_id = st.sidebar.text_input("Shotstack Template ID", value=st.session_state.template_id)
st.session_state.owner_id = st.sidebar.text_input("Shotstack Owner ID", value=st.session_state.owner_id)

st.sidebar.subheader("Gemini (Script Generation)")
if GEMINI_API_KEY_ENV:
    st.sidebar.success("Gemini API Key loaded from .env.")
else:
    st.sidebar.warning("Gemini API Key missing from .env. Please set it for script generation.")

TARGET_VIDEO_DURATION_SECONDS = st.sidebar.number_input("Target Video Duration (s)", min_value=5, max_value=300,
                                                        value=TARGET_VIDEO_DURATION_SECONDS, step=5,
                                                        key="target_dur_sb")
WORDS_PER_SECOND_ESTIMATE = st.sidebar.number_input("Words Per Second (Speaking Rate)", min_value=1.5, max_value=4.0,
                                                    value=WORDS_PER_SECOND_ESTIMATE, step=0.1, key="wps_sb")
GEMINI_MODEL_NAME = st.sidebar.selectbox("Gemini Model",
                                         options=["gemini-2.5-pro-preview-05-06","gemini-1.5-flash-latest", "gemini-1.0-pro-latest", "gemini-pro"],
                                         index=0, key="gemini_model_sb")

st.sidebar.subheader("OpenAI TTS (Narration)")
if OPENAI_API_KEY_ENV:
    st.sidebar.success("OpenAI API Key loaded from .env.")
else:
    st.sidebar.warning("OpenAI API Key missing from .env. Please set it for narration.")

SELECTED_OPENAI_TTS_VOICE = st.sidebar.selectbox(
    "OpenAI TTS Voice",
    options=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
    index=0,
    key="openai_voice_sb"
)
SELECTED_OPENAI_TTS_MODEL = st.sidebar.selectbox(
    "OpenAI TTS Model",
    options=['gpt-4o-mini-tts','tts-1', 'tts-1-hd'], # Added tts-1 as an option
    index=0,
    key="openai_tts_model_sb"
)

st.sidebar.caption(f"Using OpenAI TTS Voice: {SELECTED_OPENAI_TTS_VOICE}, Model: {SELECTED_OPENAI_TTS_MODEL}")

st.sidebar.subheader("Supabase Storage")
st.sidebar.caption(f"Uploads to: {SUPABASE_BUCKET_NAME}")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.sidebar.warning("Supabase URL/Key not configured in .env. Audio upload will fail.")
else:
    st.sidebar.success("Supabase configured for audio uploads.")

# --- Main Page Content ---
if not CONFIGURED_API_KEY:
    st.error("CRITICAL: Shotstack API Key is not configured (SHOTSTACK_API_KEY in .env).")
    st.stop()

st.markdown(
    f"Template: `{st.session_state.template_id}` | Owner: `{st.session_state.owner_id}` | Gemini: `{GEMINI_MODEL_NAME}`")
st.markdown(
    f"Target script: `{TARGET_VIDEO_DURATION_SECONDS}`s (~`{int(TARGET_VIDEO_DURATION_SECONDS * WORDS_PER_SECOND_ESTIMATE)}` words). OpenAI TTS: `{SELECTED_OPENAI_TTS_VOICE}` (`{SELECTED_OPENAI_TTS_MODEL}`)")

# --- Form Section ---
if not st.session_state.render_id or st.session_state.last_status in ["done", "failed"]:
    st.header("🎨 Customize Video Content")
    st.markdown("Modify details below. Gemini generates script, OpenAI TTS converts to speech, Supabase stores audio.")

    st.subheader("Property Details for Narration")
    st.session_state.property_description = st.text_area("Enter Property Description:",
                                                         value=st.session_state.property_description, height=150,
                                                         key="property_desc_main_input")

    st.subheader("Visual & Text Overlays")
    with st.form(key="video_customization_form_main"):
        user_inputs_from_form = {}
        col1, col2 = st.columns(2)
        for i, field_data in enumerate(ORIGINAL_DEFAULT_MERGE_FIELDS):
            if field_data["find"] == "NARRATION_AUDIO_SRC": continue
            session_key_for_display = f"user_input_{field_data['find']}"
            current_col = col1 if i % 2 == 0 else col2
            label_prefix = "🔗" if "IMAGE_SRC" in field_data['find'] or "LOGO_SRC" in field_data['find'] else "📝"
            label = f"{label_prefix} {field_data['find'].replace('_', ' ').title()}"
            user_inputs_from_form[field_data['find']] = current_col.text_input(label, value=st.session_state[
                session_key_for_display], key=f"input_form_main_{field_data['find']}")
        submit_button = st.form_submit_button(label="🚀 Generate Video with OpenAI Narration")

    if submit_button:
        for field_key, input_value in user_inputs_from_form.items():
            st.session_state[f"user_input_{field_key}"] = input_value

        st.session_state.render_id = None
        st.session_state.video_url = None
        st.session_state.last_status = None
        st.session_state.generated_script = None
        st.session_state.tts_audio_url = None

        # API keys are now directly from .env
        active_gemini_key = GEMINI_API_KEY_ENV
        active_openai_key = OPENAI_API_KEY_ENV

        if not st.session_state.template_id or not st.session_state.owner_id:
            st.error("Please ensure Shotstack Template ID and Owner ID are set.")
        elif not active_gemini_key:
            st.error("Gemini API Key is not configured in your .env file.")
        elif not active_openai_key:
            st.error("OpenAI API Key is not configured in your .env file for TTS.")
        elif not SUPABASE_URL or not SUPABASE_KEY:
            st.error("Supabase URL or Key is not configured in .env. Audio upload will fail.")
        elif not st.session_state.property_description:
            st.error("Please enter a property description for script generation.")
        else:
            current_script = generate_script_with_gemini(active_gemini_key, st.session_state.property_description,
                                                         TARGET_VIDEO_DURATION_SECONDS, WORDS_PER_SECOND_ESTIMATE,
                                                         GEMINI_MODEL_NAME)
            st.session_state.generated_script = current_script

            if not current_script or "Error:" in current_script:
                st.error(f"Script generation failed. Gemini response: {current_script}")
            else:
                st.subheader("✨ Generated Script by Gemini:")
                st.markdown(f"```text\n{current_script}\n```")

                narration_url = generate_narration_audio_url(active_openai_key, current_script,
                                                             SELECTED_OPENAI_TTS_VOICE, SELECTED_OPENAI_TTS_MODEL)
                st.session_state.tts_audio_url = narration_url
                st.session_state[
                    f"user_input_NARRATION_AUDIO_SRC"] = narration_url or ""

                if not narration_url:
                    st.warning(
                        "OpenAI TTS audio generation/upload to Supabase failed. Video might lack narration or may fail if narration is essential.")

                st.info("Preparing Shotstack request data...")
                current_merge_fields = []
                for fd in ORIGINAL_DEFAULT_MERGE_FIELDS:
                    field_value = st.session_state.get(f"user_input_{fd['find']}", fd["replace"])
                    if fd["find"] == "NARRATION_AUDIO_SRC" and field_value is None:
                        field_value = ""
                    current_merge_fields.append({"find": fd["find"], "replace": field_value})

                api_response = render_video_with_shotstack(CONFIGURED_API_KEY, st.session_state.template_id,
                                                           current_merge_fields, st.session_state.owner_id)
                if api_response and api_response.get("success"):
                    st.session_state.render_id = api_response.get("response", {}).get("id")
                    st.session_state.last_status = "submitted"
                    st.success(f"✅ Video render job submitted! Render ID: {st.session_state.render_id}")
                    st.info("Checking render progress...")
                    st.rerun()
                elif api_response:
                    st.error(f"API submission failed: {api_response.get('message', 'Unknown error')}")
                    st.json(api_response)

# --- Display Generated Script (if not rendering) ---
if st.session_state.generated_script and not st.session_state.render_id and st.session_state.last_status not in ["done",
                                                                                                                 "failed",
                                                                                                                 "submitted"]:
    st.subheader("Previously Generated Script by Gemini:")
    st.markdown(f"```text\n{st.session_state.generated_script}\n```")
    if st.session_state.tts_audio_url:
        st.markdown(f"**OpenAI TTS Audio URL (Supabase):** `{st.session_state.tts_audio_url}`")
        st.audio(st.session_state.tts_audio_url)

# --- Status Checking Section ---
if st.session_state.render_id and st.session_state.last_status not in ["done", "failed"]:
    st.header("⏳ Video Rendering Progress")
    st.write(f"Render ID: `{st.session_state.render_id}`")
    status_placeholder = st.empty()

    if st.session_state.generated_script:
        st.caption("Script used:")
        st.markdown(f"```text\n{st.session_state.generated_script}\n```")
    if st.session_state.tts_audio_url:
        st.caption(f"OpenAI TTS Audio URL used (Supabase): `{st.session_state.tts_audio_url}`")
        st.audio(st.session_state.tts_audio_url)

    with st.spinner("Fetching latest render status..."):
        status_response = get_render_status(CONFIGURED_API_KEY, st.session_state.render_id)

    if status_response and status_response.get("success"):
        render_data = status_response.get("response", {})
        current_status = render_data.get("status")
        st.session_state.last_status = current_status
        status_placeholder.info(f"Current Status: **{current_status.upper()}**")

        if current_status == "done":
            st.session_state.video_url = render_data.get("url")
            status_placeholder.success("🎉 Video rendering complete!")
            vid_col, _ = st.columns([2, 1])
            with vid_col:
                st.video(st.session_state.video_url)
            if st.button("✨ Start New Video Edit", key="new_edit_done"):
                st.session_state.render_id = None;
                st.session_state.video_url = None;
                st.session_state.last_status = None;
                st.session_state.generated_script = None;
                st.session_state.tts_audio_url = None;
                st.session_state.property_description = default_desc
                for field_data_orig in ORIGINAL_DEFAULT_MERGE_FIELDS: st.session_state[
                    f"user_input_{field_data_orig['find']}"] = "" if field_data_orig[
                                                                         'find'] == "NARRATION_AUDIO_SRC" else \
                    field_data_orig["replace"]
                st.rerun()
        elif current_status == "failed":
            error_message = render_data.get("error", "Unknown error")
            status_placeholder.error(f"☠️ Video rendering failed. Reason: {error_message}")
            st.json(render_data)
            if st.button("Try Editing Again", key="edit_again_failed"):
                st.session_state.render_id = None;
                st.session_state.video_url = None;
                st.session_state.last_status = None
                st.rerun()
        else:
            status_placeholder.info(
                f"Video is still processing ({current_status.upper()}). Page refreshes automatically.")
            time.sleep(10)
            st.rerun()
    elif status_response:
        st.error(f"Error fetching status: {status_response.get('message', 'Unknown error')}")
        st.json(status_response)
        if st.button("Refresh Status Manually", key="refresh_status_error"): st.rerun()

# --- Completed/Failed Video Display ---
elif st.session_state.video_url and st.session_state.last_status == "done":
    st.header("✅ Completed Video")
    vid_col, _ = st.columns([2, 1])
    with vid_col:
        st.video(st.session_state.video_url)
    if st.session_state.generated_script: st.caption("Script used:"); st.markdown(
        f"```text\n{st.session_state.generated_script}\n```")
    if st.session_state.tts_audio_url:
        st.caption(f"OpenAI TTS Audio URL used (Supabase): `{st.session_state.tts_audio_url}`")
        st.audio(st.session_state.tts_audio_url)
    if st.button("✨ Start New Video Edit", key="new_edit_completed"):
        st.session_state.render_id = None;
        st.session_state.video_url = None;
        st.session_state.last_status = None;
        st.session_state.generated_script = None;
        st.session_state.tts_audio_url = None;
        st.session_state.property_description = default_desc
        for field_data_orig in ORIGINAL_DEFAULT_MERGE_FIELDS: st.session_state[
            f"user_input_{field_data_orig['find']}"] = "" if field_data_orig['find'] == "NARRATION_AUDIO_SRC" else \
            field_data_orig["replace"]
        st.rerun()

elif st.session_state.last_status == "failed":
    st.error("The previous video rendering failed.")
    if st.session_state.generated_script: st.caption("Script attempted:"); st.markdown(
        f"```text\n{st.session_state.generated_script}\n```")
    if st.session_state.tts_audio_url:
        st.caption(f"OpenAI TTS Audio URL attempted (Supabase): `{st.session_state.tts_audio_url}`")
        st.audio(st.session_state.tts_audio_url)
    if st.button("Try Editing Again", key="edit_again_prev_failed"):
        st.session_state.render_id = None;
        st.session_state.video_url = None;
        st.session_state.last_status = None
        st.rerun()

# --- Footer ---
st.markdown("---")
st.caption("AI Video Editor (Stage with Gemini, OpenAI TTS & Supabase)")