# main_app_sdk_refactor.py

import streamlit as st
import requests  # Keep for Shotstack, etc.
import json
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
from supabase import create_client, Client
import mimetypes
import logging  # For potential StreamlitHandler if used

# Import the refactored HeyGen API Client
from HeyGen import HeyGenAPIClient

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Shotstack Config
CONFIGURED_SHOTSTACK_API_KEY = os.getenv("SHOTSTACK_API_KEY")
SHOTSTACK_TEMPLATE_ID_ENV = os.getenv("SHOTSTACK_TEMPLATE_ID", "f408d4a6-281b-4e73-a818-04999bce19cc")
SHOTSTACK_OWNER_ID_ENV = os.getenv("SHOTSTACK_OWNER_ID", "ttwxkrohlv")
SHOTSTACK_API_ENDPOINT = os.getenv("SHOTSTACK_API_ENDPOINT", "https://api.shotstack.io/edit/stage/templates/render")
SHOTSTACK_STATUS_ENDPOINT_TEMPLATE = os.getenv("SHOTSTACK_STATUS_ENDPOINT_TEMPLATE",
                                               "https://api.shotstack.io/edit/stage/render/{}")

# LLM & TTS Config
GEMINI_API_KEY_ENV = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY_ENV = os.getenv("OPENAI_API_KEY")
DEFAULT_OPENAI_TTS_VOICE = "alloy"
DEFAULT_OPENAI_TTS_MODEL = "tts-1"

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET_NAME = os.getenv("SUPABASE_BUCKET_NAME", "videobgm")

# Scripting Config
TARGET_VIDEO_DURATION_SECONDS = int(os.getenv("TARGET_VIDEO_DURATION_SECONDS", "25"))
WORDS_PER_SECOND_ESTIMATE = float(os.getenv("WORDS_PER_SECOND_ESTIMATE", "2.5"))

# HeyGen Configuration
HEYGEN_API_KEY_ENV = os.getenv("HEYGEN_API_KEY")
DEFAULT_HEYGEN_TALKING_PHOTO_ID_ENV = os.getenv("DEFAULT_HEYGEN_TALKING_PHOTO_ID", "63da0015b6e24aaab076f8257b3801d7")
DEFAULT_HEYGEN_VOICE_ID_ENV = os.getenv("DEFAULT_HEYGEN_VOICE_ID", "d7bbcdd6964c47bdaae26decade4a933")

# Instantiate HeyGen Client
heygen_client = None
if HEYGEN_API_KEY_ENV:
    heygen_client = HeyGenAPIClient(api_key=HEYGEN_API_KEY_ENV)
else:
    print("CRITICAL WARNING: HEYGEN_API_KEY not found. HeyGen features will not work.")

# --- Default Merge Fields ---
ORIGINAL_DEFAULT_MERGE_FIELDS = [
    {"find": "AVATAR_VIDEO", "replace": ""},
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


# --- Helper Functions (Logging, etc.) ---
def log_message(message, level="info", source="APP_MAIN"):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"LOG_STREAMLIT [{timestamp}] ({source} - {level.upper()}): {message}"
    print(log_entry)
    if "logs" not in st.session_state: st.session_state.logs = []
    st.session_state.logs.insert(0, log_entry)
    if len(st.session_state.logs) > 150: st.session_state.logs = st.session_state.logs[:150]


# --- LLM and TTS Functions ---
def generate_script_with_gemini(api_key_gemini, description, target_duration_seconds, words_per_second,
                                model_name="gemini-2.5-pro-preview-05-06"):
    log_message(f"Generating script for HeyGen Avatar (target: {target_duration_seconds}s).", "info", "GEMINI")
    if not api_key_gemini:
        st.error("Gemini API Key is missing.");
        log_message("Gemini API Key not configured.", "error", "GEMINI");
        return "Error: Gemini API Key not configured."
    try:
        genai.configure(api_key=api_key_gemini)
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
        spinner_msg = f"🤖 Generating script for HeyGen Avatar (target: ~{target_word_count} words)..."
        log_message(spinner_msg, "info", "GEMINI")
        with st.spinner(spinner_msg):
            response = model.generate_content(prompt)
        generated_text = "".join(part.text for part in response.parts if hasattr(part, 'text')) if hasattr(response,
                                                                                                           'parts') and response.parts else (
            response.text if hasattr(response, 'text') else "")
        if not generated_text:
            feedback = str(response.prompt_feedback) if hasattr(response,
                                                                'prompt_feedback') and response.prompt_feedback else "No prompt feedback."
            st.error(f"Gemini returned an empty script. Feedback: {feedback}");
            log_message(f"Gemini returned empty. Feedback: {feedback}", "error", "GEMINI");
            return "Error: Gemini empty script."
        log_message(f"Gemini script generated. Length: {len(generated_text.split())} words.", "success", "GEMINI");
        return generated_text.strip()
    except Exception as e:
        st.error(f"Error with Gemini: {e}");
        log_message(f"Error with Gemini: {e}", "error", "GEMINI");
        return f"Error: {str(e)}"


def generate_openai_tts_audio_to_file(api_key_openai, script_text, output_filepath, voice_model, tts_model):
    if not api_key_openai:
        st.error("OpenAI API Key missing.");
        log_message("OpenAI API Key not configured for TTS.", "error", "OPENAI_TTS");
        return None
    try:
        client = OpenAI(api_key=api_key_openai)
        log_message(f"Synthesizing speech (voice: {voice_model}, model: {tts_model})...", "info", "OPENAI_TTS")
        with client.audio.speech.with_streaming_response.create(model=tts_model, voice=voice_model, input=script_text,
                                                                response_format="mp3") as response:
            response.stream_to_file(output_filepath)
        log_message(f'OpenAI TTS audio to "{output_filepath}"', "success", "OPENAI_TTS");
        return output_filepath
    except Exception as e:
        st.error(f"OpenAI TTS error: {e}"); log_message(f"OpenAI TTS error: {e}", "error", "OPENAI_TTS"); return None


def upload_audio_and_get_public_url(local_filepath, filename_in_bucket):
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase URL/Key not configured.");
        log_message("Supabase URL/Key not configured.", "error", "SUPABASE");
        return None
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        content_type, _ = mimetypes.guess_type(local_filepath);
        content_type = content_type or "audio/mpeg"
        with open(local_filepath, 'rb') as f:
            log_message(
                f"Uploading '{local_filepath}' to Supabase bucket '{SUPABASE_BUCKET_NAME}' as '{filename_in_bucket}'...",
                "info", "SUPABASE")
            supabase.storage.from_(SUPABASE_BUCKET_NAME).upload(path=filename_in_bucket, file=f,
                                                                file_options={"content-type": content_type,
                                                                              "upsert": "true"})
        public_url_data = supabase.storage.from_(SUPABASE_BUCKET_NAME).get_public_url(filename_in_bucket)
        if isinstance(public_url_data, str):
            log_message(f"Supabase upload success. URL: {public_url_data}", "success", "SUPABASE");
            return public_url_data
        st.error(f"Failed to get public URL from Supabase. Response: {public_url_data}");
        log_message(f"Supabase get public URL failed. Response: {public_url_data}", "error", "SUPABASE");
        return None
    except Exception as e:
        st.error(f"Supabase error: {e}"); log_message(f"Supabase error: {e}", "error", "SUPABASE"); return None


def generate_optional_background_narration_url(openai_api_key, script_text, openai_tts_voice, openai_tts_model):
    if not script_text or "Error:" in script_text: log_message("Skipping BG narration due to script error/empty.",
                                                               "warning", "OPENAI_TTS"); return None
    local_audio_file = f"temp_bg_narration_{int(time.time())}.mp3"
    try:
        if not generate_openai_tts_audio_to_file(openai_api_key, script_text, local_audio_file, openai_tts_voice,
                                                 openai_tts_model): return None
        unique_filename_in_bucket = f"bg_narration_openai_{int(time.time())}_{os.path.basename(local_audio_file).replace(' ', '_')}"
        public_audio_url = upload_audio_and_get_public_url(local_audio_file, unique_filename_in_bucket)
        if public_audio_url:
            st.success(f"🎙️ Optional BG Narration Ready: {public_audio_url}")
        else:
            st.error("Failed to upload BG narration.")
        return public_audio_url
    finally:
        if os.path.exists(local_audio_file):
            try:
                os.remove(local_audio_file); log_message(f"Temp BG audio file '{local_audio_file}' removed.", "info",
                                                         "SYSTEM")
            except Exception as e_rem:
                st.warning(f"Could not remove temp BG audio {local_audio_file}: {e_rem}")


# --- Shotstack API Call Functions ---
def render_video_with_shotstack(api_key_to_use, template_id, merge_fields, owner_id):
    if not api_key_to_use: st.error("Shotstack API Key missing."); log_message("Shotstack API Key missing for render.",
                                                                               "error", "SHOTSTACK"); return None
    headers = {"Content-Type": "application/json", "x-api-key": api_key_to_use}
    payload = {"id": template_id, "merge": merge_fields, "owner": owner_id}
    try:
        log_message(f"Shotstack render payload: {json.dumps(payload, indent=1)}", "debug", "SHOTSTACK")
        response = requests.post(SHOTSTACK_API_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status();
        log_message(f"Shotstack render submission: {response.json()}", "info", "SHOTSTACK");
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Shotstack API error (render): {e}");
        log_message(f"Shotstack API error (render): {e}", "error", "SHOTSTACK")
        if hasattr(e, 'response') and e.response is not None: st.error(f"Shotstack API response: {e.response.text}")
        return None


def get_render_status(api_key_to_use, render_id):
    if not api_key_to_use: st.error("Shotstack API Key missing."); log_message("Shotstack API Key missing for status.",
                                                                               "error", "SHOTSTACK"); return None
    if not render_id: return None
    headers = {"x-api-key": api_key_to_use, "Accept": "application/json"}
    status_url = SHOTSTACK_STATUS_ENDPOINT_TEMPLATE.format(render_id)
    try:
        response = requests.get(status_url, headers=headers);
        response.raise_for_status()
        log_message(f"Shotstack status for {render_id}: {response.json()}", "debug", "SHOTSTACK");
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Shotstack status error: {e}");
        log_message(f"Shotstack status error for {render_id}: {e}", "error", "SHOTSTACK")
        if hasattr(e, 'response') and e.response is not None: st.error(f"Shotstack API response: {e.response.text}")
        return None


# --- HeyGen Polling function using the SDK ---
def list_heygen_group_looks_with_polling_sdk(group_id_to_poll, max_attempts=24, delay_seconds=5):
    if not heygen_client:
        log_message("HeyGen client not initialized for polling.", "error", "HEYGEN_GROUP_POLL")
        st.error("HeyGen client not available.")
        return None

    log_message(f"SDK: Polling HeyGen group '{group_id_to_poll}' for processed looks", "info", "HEYGEN_GROUP_POLL")
    EXPECTED_READY_LOOK_STATUS = "COMPLETED"  # VERIFY THIS!

    for attempt in range(1, max_attempts + 1):
        st.info(f"Polling HeyGen for look status... Attempt {attempt}/{max_attempts}")
        looks_list = heygen_client.list_avatar_group_looks(group_id=group_id_to_poll)

        if looks_list is not None:
            if looks_list:
                first_look = looks_list[0]
                look_id = first_look.get("id")
                look_status = first_look.get("status", "unknown").upper()
                log_message(
                    f"SDK Attempt {attempt}/{max_attempts}: Group '{group_id_to_poll}', Look ID: {look_id}, Status: '{look_status}'",
                    "info", "HEYGEN_GROUP_POLL")

                if look_id and look_status == EXPECTED_READY_LOOK_STATUS:
                    log_message(
                        f"SDK: Look ID {look_id} in group '{group_id_to_poll}' is READY after {attempt} attempts.",
                        "success", "HEYGEN_GROUP_POLL")
                    st.success(f"Avatar look (ID: {look_id}) is ready for video generation!")
                    return look_id
                elif look_id and look_status not in ["PENDING", "TRAINING", "PROCESSING",
                                                     "UNKNOWN"]:  # Terminal state but not desired
                    log_message(
                        f"SDK: Look ID {look_id} in group '{group_id_to_poll}' has status '{look_status}' (not {EXPECTED_READY_LOOK_STATUS}). Stopping poll.",
                        "error", "HEYGEN_GROUP_POLL")
                    st.error(
                        f"Avatar look processing finished with status '{look_status}', which is not '{EXPECTED_READY_LOOK_STATUS}'. Cannot proceed.")
                    return None

                if attempt < max_attempts:
                    st.info(
                        f"Avatar look processing (ID: {look_id or 'N/A'}, Status: {look_status}). Waiting {delay_seconds}s... (Attempt {attempt}/{max_attempts})")
                    time.sleep(delay_seconds)
                else:
                    log_message(f"SDK: Max polling attempts. Look ID: {look_id or 'N/A'}, Status: {look_status}.",
                                "error", "HEYGEN_GROUP_POLL")
                    st.error(
                        f"Timeout: Avatar look (ID: {look_id or 'N/A'}) not '{EXPECTED_READY_LOOK_STATUS}' after {max_attempts * delay_seconds}s.")
                    return None
            else:  # Empty list
                log_message(f"SDK: No looks found in group '{group_id_to_poll}' on attempt {attempt}.", "warning",
                            "HEYGEN_GROUP_POLL")
                if attempt < max_attempts:
                    st.warning(
                        f"No looks found yet. Waiting {delay_seconds}s... (Attempt {attempt}/{max_attempts})"); time.sleep(
                        delay_seconds)
                else:
                    st.error(f"No looks found in group {group_id_to_poll} after {max_attempts} attempts."); return None
        else:  # SDK call failed
            log_message(f"SDK: Failed to list HeyGen group looks for '{group_id_to_poll}' on attempt {attempt}.",
                        "error", "HEYGEN_GROUP_POLL")
            st.error("Error communicating with HeyGen to list looks.")
            if attempt < max_attempts:
                st.warning(f"Retrying in {delay_seconds}s..."); time.sleep(delay_seconds)
            else:
                return None
    return None


# --- Streamlit App Interface ---
st.set_page_config(page_title="AI Video Suite SDK Refactor v2", layout="wide")
st.title("🎬 AI Video Production Suite (SDK Refactor v2)")

# Initialize session state
for field_data in ORIGINAL_DEFAULT_MERGE_FIELDS:
    session_key = f"user_input_{field_data['find']}"
    if session_key not in st.session_state: st.session_state[session_key] = field_data["replace"]
default_desc = "Spacious 3-bedroom apartment with stunning city views, modern kitchen, and a large balcony. Located in a prime downtown area, close to parks and amenities. Features hardwood floors, en-suite master bathroom, and ample storage space. Perfect for families or professionals seeking a vibrant urban lifestyle."
if 'property_description' not in st.session_state: st.session_state.property_description = default_desc
if 'avatar_script' not in st.session_state: st.session_state.avatar_script = None
if 'optional_bg_narration_script' not in st.session_state: st.session_state.optional_bg_narration_script = ""
if 'optional_bg_narration_audio_url' not in st.session_state: st.session_state.optional_bg_narration_audio_url = None
if 'shotstack_template_id' not in st.session_state: st.session_state.shotstack_template_id = SHOTSTACK_TEMPLATE_ID_ENV
if 'shotstack_owner_id' not in st.session_state: st.session_state.shotstack_owner_id = SHOTSTACK_OWNER_ID_ENV
if 'shotstack_render_id' not in st.session_state: st.session_state.shotstack_render_id = None
if 'shotstack_video_url' not in st.session_state: st.session_state.shotstack_video_url = None
if 'shotstack_last_status' not in st.session_state: st.session_state.shotstack_last_status = None
if 'ui_heygen_default_talking_photo_id' not in st.session_state: st.session_state.ui_heygen_default_talking_photo_id = DEFAULT_HEYGEN_TALKING_PHOTO_ID_ENV
if 'ui_heygen_voice_id' not in st.session_state: st.session_state.ui_heygen_voice_id = DEFAULT_HEYGEN_VOICE_ID_ENV
if 'ui_heygen_test_mode' not in st.session_state: st.session_state.ui_heygen_test_mode = False
if 'ui_heygen_add_captions' not in st.session_state: st.session_state.ui_heygen_add_captions = False
if 'ui_heygen_dimension' not in st.session_state: st.session_state.ui_heygen_dimension = "720p"
if 'heygen_video_id' not in st.session_state: st.session_state.heygen_video_id = None
if 'heygen_video_url' not in st.session_state: st.session_state.heygen_video_url = None
if 'heygen_video_status' not in st.session_state: st.session_state.heygen_video_status = None
if 'heygen_temp_group_id_for_deletion' not in st.session_state: st.session_state.heygen_temp_group_id_for_deletion = None
if 'ui_enable_optional_bg_narration' not in st.session_state: st.session_state.ui_enable_optional_bg_narration = False
if 'current_process_stage' not in st.session_state: st.session_state.current_process_stage = "idle"
if 'logs' not in st.session_state: st.session_state.logs = []
if 'uploaded_avatar_photo_bytes' not in st.session_state: st.session_state.uploaded_avatar_photo_bytes = None
if 'uploaded_avatar_photo_name' not in st.session_state: st.session_state.uploaded_avatar_photo_name = None
if 'final_talking_photo_id_for_heygen' not in st.session_state: st.session_state.final_talking_photo_id_for_heygen = None

# --- Sidebar ---
st.sidebar.header("API & General Configuration")
st.sidebar.subheader("HeyGen")
if HEYGEN_API_KEY_ENV and heygen_client:
    st.sidebar.success("HeyGen API Key loaded & Client Initialized.")
else:
    st.sidebar.error("HeyGen API Key missing or Client Failed. HeyGen features will fail.")
st.session_state.ui_heygen_default_talking_photo_id = st.sidebar.text_input("Default HeyGen Talking Photo ID",
                                                                            value=st.session_state.ui_heygen_default_talking_photo_id,
                                                                            key="sb_hg_default_tp")
st.session_state.ui_heygen_voice_id = st.sidebar.text_input("HeyGen Voice ID (for Avatar)",
                                                            value=st.session_state.ui_heygen_voice_id,
                                                            key="sb_hg_voice")

st.sidebar.subheader("Shotstack (Stage)")
st.session_state.shotstack_template_id = st.sidebar.text_input("Shotstack Template ID",
                                                               value=st.session_state.shotstack_template_id,
                                                               key="sb_ss_template")
st.session_state.shotstack_owner_id = st.sidebar.text_input("Shotstack Owner ID",
                                                            value=st.session_state.shotstack_owner_id,
                                                            key="sb_ss_owner")
if CONFIGURED_SHOTSTACK_API_KEY:
    st.sidebar.success("Shotstack API Key loaded.")
else:
    st.sidebar.warning("Shotstack API Key missing. Shotstack features will fail.")

st.sidebar.subheader("Gemini (for Avatar Script)")
if GEMINI_API_KEY_ENV:
    st.sidebar.success("Gemini API Key loaded.")
else:
    st.sidebar.warning("Gemini API Key missing. Avatar script generation will fail.")
TARGET_VIDEO_DURATION_SECONDS = st.sidebar.number_input("Target Avatar Script Duration (s)", min_value=5, max_value=120,
                                                        value=TARGET_VIDEO_DURATION_SECONDS, step=5,
                                                        key="target_dur_sb_sdk2")
WORDS_PER_SECOND_ESTIMATE = st.sidebar.number_input("Words Per Second (Avatar Rate)", min_value=1.5, max_value=4.0,
                                                    value=WORDS_PER_SECOND_ESTIMATE, step=0.1, key="wps_sb_sdk2")
GEMINI_MODEL_NAME = st.sidebar.selectbox("Gemini Model", options=["gemini-2.5-pro-preview-05-06"], index=0,
                                         key="gemini_model_sb_sdk2")

st.sidebar.subheader("OpenAI TTS (Optional BG Narration)")
if OPENAI_API_KEY_ENV:
    st.sidebar.success("OpenAI API Key loaded.")
else:
    st.sidebar.warning("OpenAI API Key missing. Optional narration will fail if enabled.")
st.session_state.ui_enable_optional_bg_narration = st.sidebar.checkbox("Enable Optional BG Narration",
                                                                       value=st.session_state.ui_enable_optional_bg_narration,
                                                                       key="sb_opt_narr_cb")
if st.session_state.ui_enable_optional_bg_narration:
    SELECTED_OPENAI_TTS_VOICE = st.sidebar.selectbox("OpenAI TTS Voice",
                                                     options=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
                                                     index=0, key="openai_voice_sb_sdk2")
    SELECTED_OPENAI_TTS_MODEL = st.sidebar.selectbox("OpenAI TTS Model", options=['tts-1', 'tts-1-hd'], index=0,
                                                     key="openai_tts_model_sb_sdk2")

st.sidebar.subheader("Supabase Storage (Optional Narration)")
st.sidebar.caption(f"Uploads to bucket: {SUPABASE_BUCKET_NAME}")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.sidebar.warning("Supabase URL/Key not configured. Upload will fail.")
else:
    st.sidebar.success("Supabase configured.")

# --- Main Page Content ---
overall_status_placeholder = st.empty()
can_show_form = st.session_state.current_process_stage in ["idle", "done", "failed"]

if can_show_form:
    st.header("🎬 Video Production Configuration (SDK Refactor v2)")
    st.subheader("🏠 Property Details")
    st.session_state.property_description = st.text_area("Property Description (for Avatar's script):",
                                                         value=st.session_state.property_description, height=150,
                                                         key="property_desc_main_input_sdk2")

    with st.expander("👤 HeyGen Talking Avatar Settings", expanded=True):
        st.write("Upload photo for custom avatar. If none, Default Talking Photo ID (sidebar) is used.")
        uploaded_photo = st.file_uploader("Upload photo for avatar (JPG, PNG):", type=['jpg', 'jpeg', 'png'],
                                          key="heygen_photo_uploader_sdk2")
        if uploaded_photo is not None:
            st.session_state.uploaded_avatar_photo_bytes = uploaded_photo.getvalue()
            st.session_state.uploaded_avatar_photo_name = uploaded_photo.name
            st.success(f"Photo '{uploaded_photo.name}' staged.")
        elif st.session_state.uploaded_avatar_photo_name:  # Persist staged photo info
            st.info(f"Previously selected photo '{st.session_state.uploaded_avatar_photo_name}' staged.")

    if st.session_state.ui_enable_optional_bg_narration:
        with st.expander("🎤 Optional Background Narration Script", expanded=False):
            st.session_state.optional_bg_narration_script = st.text_area(
                "BG narration script (OR leave blank for generic greeting):",
                value=st.session_state.optional_bg_narration_script, height=100, key="optional_bg_script_input_sdk2")

    with st.expander("🖼️ Shotstack Visual & Text Overlays", expanded=False):
        with st.form(key="shotstack_merge_fields_form_sdk2"):
            user_inputs_from_form = {}
            cols = st.columns(2);
            col_idx = 0
            for field_data in ORIGINAL_DEFAULT_MERGE_FIELDS:
                if field_data["find"] in ["NARRATION_AUDIO_SRC", "AVATAR_VIDEO"]:
                    user_inputs_from_form[field_data["find"]] = st.session_state.get(f"user_input_{field_data['find']}",
                                                                                     field_data["replace"])
                    continue
                session_key_for_display = f"user_input_{field_data['find']}"
                current_col = cols[col_idx % 2]
                label_prefix = "🔗" if "IMAGE_SRC" in field_data['find'] or "LOGO_SRC" in field_data['find'] else "📝"
                label = f"{label_prefix} {field_data['find'].replace('_', ' ').title()}"
                user_inputs_from_form[field_data['find']] = current_col.text_input(label, value=st.session_state.get(
                    session_key_for_display, field_data["replace"]),
                                                                                   key=f"input_form_shotstack_{field_data['find']}_sdk2")
                col_idx += 1
            submit_button = st.form_submit_button(label="🚀 Generate Full Video")

    if submit_button:
        for field_key, input_value in user_inputs_from_form.items():
            if field_key not in ["AVATAR_VIDEO", "NARRATION_AUDIO_SRC"]:
                st.session_state[f"user_input_{field_key}"] = input_value
        # Reset states
        st.session_state.shotstack_render_id = None;
        st.session_state.shotstack_video_url = None;
        st.session_state.shotstack_last_status = None;
        st.session_state.avatar_script = None;
        st.session_state.optional_bg_narration_audio_url = None;
        st.session_state.heygen_video_id = None;
        st.session_state.heygen_video_url = None;
        st.session_state.heygen_video_status = None;
        st.session_state.final_talking_photo_id_for_heygen = None;
        st.session_state.heygen_temp_group_id_for_deletion = None;  # Ensure this is reset
        st.session_state.logs = []

        valid_run = True
        if not heygen_client: st.error("HeyGen Client not initialized (API Key issue?)."); valid_run = False
        if not st.session_state.property_description: st.error("Property description is required."); valid_run = False
        if not st.session_state.uploaded_avatar_photo_bytes and not st.session_state.ui_heygen_default_talking_photo_id: st.error(
            "Upload a photo OR set a Default HeyGen Talking Photo ID."); valid_run = False
        if not st.session_state.ui_heygen_voice_id: st.error(
            "HeyGen Voice ID for avatar is missing."); valid_run = False
        # ... (other API key and config checks)
        if not GEMINI_API_KEY_ENV: st.error("Gemini API Key is missing."); valid_run = False
        if st.session_state.ui_enable_optional_bg_narration and not OPENAI_API_KEY_ENV: st.error(
            "OpenAI API Key for BG narration missing."); valid_run = False
        if st.session_state.ui_enable_optional_bg_narration and (not SUPABASE_URL or not SUPABASE_KEY): st.error(
            "Supabase URL/Key for BG audio missing."); valid_run = False
        if not CONFIGURED_SHOTSTACK_API_KEY: st.error("Shotstack API Key is missing."); valid_run = False
        if not st.session_state.shotstack_template_id or not st.session_state.shotstack_owner_id: st.error(
            "Shotstack Template/Owner ID missing."); valid_run = False

        if valid_run:
            log_message("Starting video generation pipeline (SDK Refactor v2).", "info", "SYSTEM")
            st.session_state.current_process_stage = "avatar_script_generation"
            st.rerun()
        else:
            log_message("Validation failed. Cannot start generation.", "error", "SYSTEM")

# --- Main Processing Logic (State Machine using SDK) ---
if st.session_state.current_process_stage == "avatar_script_generation":
    overall_status_placeholder.info("📝 Generating script for HeyGen Avatar...")
    # ... (same as before)
    with st.spinner("Generating avatar script with Gemini..."):
        script_for_avatar = generate_script_with_gemini(GEMINI_API_KEY_ENV, st.session_state.property_description,
                                                        TARGET_VIDEO_DURATION_SECONDS, WORDS_PER_SECOND_ESTIMATE,
                                                        GEMINI_MODEL_NAME)
    st.session_state.avatar_script = script_for_avatar
    if not script_for_avatar or "Error:" in script_for_avatar:
        st.error(f"Avatar script generation failed: {script_for_avatar}");
        log_message(f"Avatar script gen failed: {script_for_avatar}", "error", "GEMINI_PROCESS")
        st.session_state.current_process_stage = "failed"
    else:
        log_message("Avatar script generated. Proceeding to HeyGen avatar setup.", "info", "SYSTEM")
        st.session_state.current_process_stage = "heygen_avatar_setup"
    st.rerun()


elif st.session_state.current_process_stage == "heygen_avatar_setup":
    overall_status_placeholder.info("👤 Setting up HeyGen Avatar (SDK)...")
    if not heygen_client: st.error(
        "HeyGen Client Error."); st.session_state.current_process_stage = "failed"; st.rerun()

    st.session_state.heygen_temp_group_id_for_deletion = None  # Ensure reset at start of this stage

    if st.session_state.uploaded_avatar_photo_bytes and st.session_state.uploaded_avatar_photo_name:
        image_key_from_upload = None
        with st.spinner(f"SDK: Uploading '{st.session_state.uploaded_avatar_photo_name}' to HeyGen assets..."):
            image_key_from_upload = heygen_client.upload_asset_from_bytes_get_image_key(
                file_bytes=st.session_state.uploaded_avatar_photo_bytes,
                file_name=st.session_state.uploaded_avatar_photo_name)

        if image_key_from_upload:
            log_message(f"SDK: Photo asset uploaded. Image Key: {image_key_from_upload}. Creating group.", "info",
                        "HEYGEN_SETUP")
            group_name = f"TempGroup_{st.session_state.user_input_PRODUCT_NAME or 'Video'}_{int(time.time())}"
            group_id_created = None
            with st.spinner(f"SDK: Creating HeyGen Avatar Group '{group_name}'..."):
                group_id_created = heygen_client.create_photo_avatar_group(name=group_name,
                                                                           image_key=image_key_from_upload)

            if group_id_created:
                st.session_state.heygen_temp_group_id_for_deletion = group_id_created  # Store for later deletion
                log_message(f"SDK: Group created (ID: {group_id_created}). Polling for look processing.", "info",
                            "HEYGEN_SETUP")
                processed_look_id = None
                with st.spinner(f"SDK: Waiting for HeyGen to process avatar in group (may take a minute)..."):
                    processed_look_id = list_heygen_group_looks_with_polling_sdk(group_id_to_poll=group_id_created)

                if processed_look_id:
                    st.session_state.final_talking_photo_id_for_heygen = processed_look_id
                    log_message(f"SDK: Using Talking Photo ID from group look: {processed_look_id}", "info",
                                "HEYGEN_SETUP")
                    st.session_state.current_process_stage = "heygen_video_processing"
                else:
                    st.error("SDK: Failed to get a usable Talking Photo ID from the new avatar group after polling.")
                    log_message("SDK: Failed to get Talking Photo ID from group look after polling.", "error",
                                "HEYGEN_SETUP")
                    st.session_state.current_process_stage = "failed"
            else:
                st.error("SDK: Failed to create HeyGen Avatar Group.");
                st.session_state.current_process_stage = "failed"
        else:
            st.error("SDK: Failed to upload photo to HeyGen assets.");
            st.session_state.current_process_stage = "failed"
    else:  # Use default
        default_tp_id = st.session_state.ui_heygen_default_talking_photo_id
        if not default_tp_id:
            st.error("Default HeyGen Talking Photo ID not set and no photo uploaded.");
            st.session_state.current_process_stage = "failed"
        else:
            st.session_state.final_talking_photo_id_for_heygen = default_tp_id
            log_message(f"SDK: Using default HeyGen Talking Photo ID: {default_tp_id}", "info", "HEYGEN_SETUP")
            st.session_state.current_process_stage = "heygen_video_processing"
    st.rerun()

elif st.session_state.current_process_stage == "heygen_video_processing":
    overall_status_placeholder.info("🗣️ Processing HeyGen Avatar Video (SDK)...")
    if not heygen_client: st.error(
        "HeyGen Client Error."); st.session_state.current_process_stage = "failed"; st.rerun()

    if not st.session_state.heygen_video_id:
        if not st.session_state.avatar_script or not st.session_state.final_talking_photo_id_for_heygen:
            st.error("Missing script or Talking Photo ID for HeyGen video.");
            st.session_state.current_process_stage = "failed";
            st.rerun()
        with st.spinner("SDK: Submitting video to HeyGen..."):
            heygen_vid_id_from_sdk = heygen_client.generate_video_with_photo_or_avatar(
                text_script=st.session_state.avatar_script, voice_id=st.session_state.ui_heygen_voice_id,
                title=f"Avatar for {st.session_state.user_input_PRODUCT_NAME or 'Video'}",
                test_mode=st.session_state.ui_heygen_test_mode, add_caption=st.session_state.ui_heygen_add_captions,
                dimension_preset=st.session_state.ui_heygen_dimension,
                talking_photo_id=st.session_state.final_talking_photo_id_for_heygen)
        if heygen_vid_id_from_sdk:
            st.session_state.heygen_video_id = heygen_vid_id_from_sdk;
            st.session_state.heygen_video_status = "submitted"
            log_message(f"SDK: HeyGen video submitted. ID: {heygen_vid_id_from_sdk}", "info", "HEYGEN_PROCESS")
        else:
            st.error("SDK: Failed to submit HeyGen video job."); st.session_state.current_process_stage = "failed"
        st.rerun()

    elif st.session_state.heygen_video_id and st.session_state.heygen_video_status != "completed":
        with st.spinner(
                f"SDK: Waiting for HeyGen video (ID: {st.session_state.heygen_video_id}). Status: {st.session_state.heygen_video_status or 'checking'}..."):
            status, url, error_data = heygen_client.check_video_status(video_id=st.session_state.heygen_video_id)
        st.session_state.heygen_video_status = status
        if status == "completed":
            st.session_state.heygen_video_url = url;
            st.session_state.user_input_AVATAR_VIDEO = url
            log_message(f"SDK: HeyGen video completed. URL: {url}", "success", "HEYGEN_PROCESS")
            st.success(f"✅ HeyGen Avatar Video Ready: {url}");
            if url: st.video(url)

            if st.session_state.heygen_temp_group_id_for_deletion:
                log_message(
                    f"SDK: Deleting temp HeyGen avatar group: {st.session_state.heygen_temp_group_id_for_deletion}",
                    "info", "HEYGEN_CLEANUP")
                with st.spinner(
                        f"SDK: Deleting temp HeyGen group (ID: {st.session_state.heygen_temp_group_id_for_deletion})..."):
                    delete_success = heygen_client.delete_photo_avatar_group(
                        group_id=st.session_state.heygen_temp_group_id_for_deletion)  # Uses DELETE path param
                if delete_success:
                    log_message(f"SDK: Successfully deleted group {st.session_state.heygen_temp_group_id_for_deletion}",
                                "info", "HEYGEN_CLEANUP")
                else:
                    log_message(
                        f"SDK: Failed to delete group {st.session_state.heygen_temp_group_id_for_deletion}. Manual check may be needed.",
                        "warning", "HEYGEN_CLEANUP")
                st.session_state.heygen_temp_group_id_for_deletion = None

            if st.session_state.ui_enable_optional_bg_narration:
                st.session_state.current_process_stage = "optional_narration_processing"
            else:
                st.session_state.user_input_NARRATION_AUDIO_SRC = ""; st.session_state.current_process_stage = "shotstack_processing"
            time.sleep(1)
        elif status in ["failed", "error"]:
            err_msg = error_data.get("message", "Unknown HeyGen error") if isinstance(error_data, dict) else str(
                error_data)
            st.error(f"SDK: HeyGen video failed. Status: {status}, Error: {err_msg}");
            log_message(f"SDK: HeyGen video failed: {status}, {err_msg}", "error", "HEYGEN_PROCESS")
            st.session_state.current_process_stage = "failed"
        else:
            log_message(f"SDK: HeyGen video status: {status}. Polling.", "info", "HEYGEN_PROCESS"); time.sleep(10)
        st.rerun()

elif st.session_state.current_process_stage == "optional_narration_processing":
    # ... (This stage remains the same)
    overall_status_placeholder.info("🎤 Processing Optional Background Narration...")
    nar_script_for_bg = st.session_state.optional_bg_narration_script
    if not nar_script_for_bg:
        nar_script_for_bg = f"Welcome! Discover more about {st.session_state.user_input_PRODUCT_NAME or 'this amazing opportunity'}."
        log_message(f"Using default script for optional BG narration: '{nar_script_for_bg}'", "info", "OPENAI_TTS")
    with st.spinner("Generating and uploading optional BG narration audio..."):
        bg_tts_url = generate_optional_background_narration_url(OPENAI_API_KEY_ENV, nar_script_for_bg,
                                                                SELECTED_OPENAI_TTS_VOICE, SELECTED_OPENAI_TTS_MODEL)
    st.session_state.optional_bg_narration_audio_url = bg_tts_url;
    st.session_state.user_input_NARRATION_AUDIO_SRC = bg_tts_url or ""
    if bg_tts_url:
        st.success(f"✅ Optional BG Narration Ready: {bg_tts_url}"); st.audio(bg_tts_url)
    else:
        st.warning("Optional BG narration audio generation/upload failed."); log_message(
            "Optional BG narration failed.", "warning", "OPENAI_TTS/SUPABASE")
    st.session_state.current_process_stage = "shotstack_processing";
    time.sleep(1);
    st.rerun()


elif st.session_state.current_process_stage == "shotstack_processing":
    # ... (This stage remains the same)
    overall_status_placeholder.info("🎞️ Processing Final Video with Shotstack...")
    if not st.session_state.shotstack_render_id:
        current_merge_fields = []
        for fd in ORIGINAL_DEFAULT_MERGE_FIELDS:
            field_value = st.session_state.get(f"user_input_{fd['find']}", fd["replace"]);
            field_value = "" if field_value is None else field_value
            current_merge_fields.append({"find": fd["find"], "replace": field_value})
        log_message(f"Final merge fields for Shotstack: {json.dumps(current_merge_fields, indent=1)}", "debug",
                    "SHOTSTACK")
        with st.spinner("Submitting video to Shotstack..."):
            api_response = render_video_with_shotstack(CONFIGURED_SHOTSTACK_API_KEY,
                                                       st.session_state.shotstack_template_id, current_merge_fields,
                                                       st.session_state.shotstack_owner_id)
        if api_response and api_response.get("success"):
            st.session_state.shotstack_render_id = api_response.get("response", {}).get("id");
            st.session_state.shotstack_last_status = "submitted"
            st.success(f"✅ Shotstack job submitted! ID: {st.session_state.shotstack_render_id}");
            log_message(f"Shotstack job submitted. ID: {st.session_state.shotstack_render_id}", "info", "SHOTSTACK")
        elif api_response:
            st.error(f"Shotstack API submission failed: {api_response.get('message', 'Unknown error')}");
            log_message(f"Shotstack submission failed: {api_response.get('message', 'Unknown error')}", "error",
                        "SHOTSTACK");
            st.json(api_response)
            st.session_state.current_process_stage = "failed"
        else:
            st.error("Shotstack API submission failed (no response)."); log_message(
                "Shotstack API submission failed (no func response).", "error",
                "SHOTSTACK"); st.session_state.current_process_stage = "failed"
        st.rerun()
    elif st.session_state.shotstack_render_id and st.session_state.shotstack_last_status != "done":
        with st.spinner(
                f"Waiting for Shotstack (ID: {st.session_state.shotstack_render_id}). Status: {st.session_state.shotstack_last_status or 'checking'}..."):
            status_response = get_render_status(CONFIGURED_SHOTSTACK_API_KEY, st.session_state.shotstack_render_id)
        if status_response and status_response.get("success"):
            render_data = status_response.get("response", {});
            current_status = render_data.get("status");
            st.session_state.shotstack_last_status = current_status
            if current_status == "done":
                st.session_state.shotstack_video_url = render_data.get("url");
                st.success("🎉 Shotstack Video Complete!");
                log_message(f"Shotstack video completed. URL: {st.session_state.shotstack_video_url}", "success",
                            "SHOTSTACK")
                st.session_state.current_process_stage = "done"
            elif current_status == "failed":
                error_message = render_data.get("error", "Unknown Shotstack error");
                st.error(f"☠️ Shotstack rendering failed: {error_message}");
                log_message(f"Shotstack video failed: {error_message}", "error", "SHOTSTACK");
                st.json(render_data)
                st.session_state.current_process_stage = "failed"
            else:
                log_message(f"Shotstack video status: {current_status}. Polling.", "info", "SHOTSTACK"); time.sleep(10)
        elif status_response:
            st.error(f"Error fetching Shotstack status: {status_response.get('message', 'Unknown')}");
            log_message(f"Error Shotstack status: {status_response.get('message', 'Unknown')}", "error", "SHOTSTACK");
            st.json(status_response);
            time.sleep(10)
        else:
            st.error("Failed to fetch Shotstack status (no func response)."); log_message(
                "Failed Shotstack status (no func response). Retrying.", "warning", "SHOTSTACK"); time.sleep(10)
        st.rerun()

# --- Display Final Results or Failure Message ---
if st.session_state.current_process_stage == "done":
    overall_status_placeholder.empty();
    st.header("🎉 Video Production Complete!")
    if st.session_state.heygen_video_url:
        with st.expander("🗣️ HeyGen Avatar Video (Used in Final)", expanded=True): st.video(
            st.session_state.heygen_video_url)
    if st.session_state.avatar_script:
        with st.expander("📜 Avatar Script (Gemini)", expanded=False): st.markdown(
            f"```text\n{st.session_state.avatar_script}\n```")
    if st.session_state.optional_bg_narration_audio_url:
        with st.expander("🎤 Optional Background Narration Audio", expanded=False): st.audio(
            st.session_state.optional_bg_narration_audio_url)
    st.subheader("✅ Final Composed Video (Shotstack):")
    if st.session_state.shotstack_video_url:
        st.video(st.session_state.shotstack_video_url)
    else:
        st.warning("Shotstack video URL not available. Check logs.")
    if st.button("✨ Create Another Video", key="new_video_done_sdk2"):
        # Reset all relevant session state variables
        st.session_state.current_process_stage = "idle"
        st.session_state.property_description = default_desc
        st.session_state.avatar_script = None
        st.session_state.optional_bg_narration_script = ""
        st.session_state.optional_bg_narration_audio_url = None
        st.session_state.shotstack_render_id = None
        st.session_state.shotstack_video_url = None
        st.session_state.shotstack_last_status = None
        st.session_state.heygen_video_id = None
        st.session_state.heygen_video_url = None
        st.session_state.heygen_video_status = None
        st.session_state.uploaded_avatar_photo_bytes = None
        st.session_state.uploaded_avatar_photo_name = None
        st.session_state.heygen_temp_group_id_for_deletion = None
        st.session_state.final_talking_photo_id_for_heygen = None
        st.session_state.logs = []
        for field_data_orig in ORIGINAL_DEFAULT_MERGE_FIELDS: st.session_state[
            f"user_input_{field_data_orig['find']}"] = field_data_orig["replace"]
        st.rerun()

elif st.session_state.current_process_stage == "failed":
    overall_status_placeholder.empty();
    st.header("☠️ Video Production Failed")
    st.error("Error during video production. Check logs and API dashboards.")
    if st.session_state.avatar_script and isinstance(st.session_state.avatar_script, str):
        with st.expander("📜 Avatar Script (Gemini)", expanded=False): st.code(st.session_state.avatar_script,
                                                                              language='text')
    if st.session_state.heygen_video_status and st.session_state.heygen_video_status not in ["completed", None,
                                                                                             "submitted"]: st.write(
        f"HeyGen Status: `{st.session_state.heygen_video_status}`")
    if st.session_state.shotstack_last_status and st.session_state.shotstack_last_status not in ["done", None,
                                                                                                 "submitted"]: st.write(
        f"Shotstack Status: `{st.session_state.shotstack_last_status}`")
    if st.button("🔄 Try Again / Modify Settings", key="try_again_failed_sdk2"):
        st.session_state.current_process_stage = "idle"
        # Selective reset for retry: Keep inputs, clear processing variables
        st.session_state.shotstack_render_id = None;
        st.session_state.shotstack_video_url = None;
        st.session_state.shotstack_last_status = None;
        st.session_state.heygen_video_id = None;
        st.session_state.heygen_video_status = None;
        st.session_state.heygen_temp_group_id_for_deletion = None;
        st.session_state.final_talking_photo_id_for_heygen = None;  # Re-determine this in heygen_avatar_setup
        # Do not clear uploaded_avatar_photo_bytes/name so user doesn't have to re-upload if only a later stage failed.
        # Do not clear property_description or other user inputs.
        st.session_state.logs = []  # Clear logs for new attempt
        st.rerun()

# --- Log Display Area ---
if st.session_state.logs:
    with st.expander("📋 View Processing Logs",
                     expanded=True if st.session_state.current_process_stage != "idle" else False):  # Expand if processing
        st.text_area("Logs", value="\n".join(st.session_state.logs), height=300, disabled=True,
                     key="log_display_area_sdk2")
st.markdown("---");
st.caption("AI Video Production Suite - SDK Refactor v2.0")