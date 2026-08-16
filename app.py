import os
import json
import uuid
from datetime import datetime

import streamlit as st

from modules import utils
from modules import enrichment
from modules import email_generator
from modules import gmail_sender
from modules import contact_tracker

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "hf_token": "",
    "rapidapi_key": "",
    "gmail_creds": "",
}

SIDEBAR_OPTIONS = ["Generate Email", "Contact Tracker", "Email History", "Settings"]


def init_session_state():
    keys = {
        "page": "Generate Email",
        "mode": "LinkedIn Post / Message",
        "settings": None,
        "resume_content": "",
        "details_content": "",
        "extracted_entities": {},
        "current_output": None,
        "email_history": [],
        "enrichment_cache": {},
        "show_send_confirmation": False,
        "send_followups": False,
    }
    for k, v in keys.items():
        if k not in st.session_state:
            st.session_state[k] = v


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_profile_files():
    resume_path = "user_profile/resume.txt"
    details_path = "user_profile/additional_details.txt"
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            st.session_state.resume_content = f.read()
    if os.path.exists(details_path):
        with open(details_path, "r", encoding="utf-8") as f:
            st.session_state.details_content = f.read()


def load_email_history():
    if os.path.exists("email_history.json"):
        try:
            with open("email_history.json", "r") as f:
                st.session_state.email_history = json.load(f)
        except json.JSONDecodeError:
            st.session_state.email_history = []


def save_email_history():
    with open("email_history.json", "w") as f:
        json.dump(st.session_state.email_history, f, indent=2)


def add_to_history(entry):
    entry["id"] = str(uuid.uuid4())
    entry["timestamp"] = datetime.utcnow().isoformat()
    st.session_state.email_history.append(entry)
    save_email_history()


def update_history_sent(entry_id):
    for entry in st.session_state.email_history:
        if entry.get("id") == entry_id:
            entry["sent"] = True
            entry["sent_at"] = datetime.utcnow().isoformat()
            break
    save_email_history()


def save_uploaded_file(uploaded, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())
    load_profile_files()


def get_context_for_generation(entities=None, manual=None, mode="linkedin_post"):
    ctx = {}
    ctx["resume"] = st.session_state.resume_content or "Not available"
    ctx["additional_details"] = st.session_state.details_content or "Not available"
    ctx["source_type"] = mode
    if mode == "linkedin_post" and entities:
        ctx["recipient_email"] = entities.get("primary_email") or entities.get("confirmed_email", "")
        ctx["recipient_name"] = entities.get("recruiter_name", "")
        ctx["recipient_title"] = entities.get("job_title", "")
        ctx["hiring_company_name"] = entities.get("confirmed_company") or entities.get("hiring_company", "")
        ctx["job_description"] = entities.get("job_description", "")
        ctx["additional_context"] = entities.get("raw_text", "")
        ctx["poster_name"] = entities.get("person_profile", {}).get("full_name", "")
        ctx["poster_current_role"] = entities.get("person_profile", {}).get("current_role", "")
        ctx["poster_headline"] = entities.get("person_profile", {}).get("headline", "")
        ctx["poster_summary"] = entities.get("person_profile", {}).get("summary", "")
        ctx["poster_skills"] = entities.get("person_profile", {}).get("skills", [])
        company = entities.get("company_profile", {})
        ctx["company_description"] = company.get("description", "")
        ctx["company_industry"] = company.get("industry", "")
        ctx["company_stage"] = company.get("funding_stage", "")
        ctx["company_recent_updates"] = company.get("recent_updates", [])
        ctx["company_tagline"] = company.get("tagline", "")
        ctx["company_specialities"] = company.get("specialities", [])
        ctx["company_website"] = company.get("website", "")
    elif mode == "manual_entry" and manual:
        ctx["recipient_email"] = manual.get("email", "")
        ctx["recipient_name"] = manual.get("name", "")
        ctx["recipient_title"] = manual.get("title", "")
        ctx["hiring_company_name"] = manual.get("company_name", "")
        ctx["company_description"] = manual.get("company_description", "")
        ctx["job_description"] = manual.get("job_description", "")
        ctx["additional_context"] = manual.get("additional_context", "")
    return ctx


def generate_email(context):
    hf_token = (st.session_state.settings or {}).get("hf_token", "")
    if not hf_token:
        st.error("Hugging Face API token not configured. Please add it in Settings.")
        return None
    try:
        system_prompt = email_generator.load_system_prompt()
    except FileNotFoundError:
        st.error("System prompt file not found: prompts/cold_email_prompt.txt")
        return None
    user_prompt = email_generator.build_user_prompt(context)
    with st.spinner("Generating email with Qwen3-32B..."):
        try:
            raw = email_generator.call_llm(system_prompt, user_prompt, hf_token)
        except Exception as e:
            st.error(f"LLM API error: {e}")
            return None
    result = email_generator.parse_llm_output(raw)
    return result


def render_settings_screen():
    st.header("Settings")
    settings = st.session_state.settings or dict(DEFAULT_SETTINGS)
    with st.expander("Candidate Profile", expanded=True):
        resume_ok = os.path.exists("user_profile/resume.txt")
        details_ok = os.path.exists("user_profile/additional_details.txt")
        st.markdown(
            f"**Resume:** {'| Loaded' if resume_ok else 'x Not uploaded'}"
        )
        st.markdown(
            f"**Additional Details:** {'| Loaded' if details_ok else 'x Not uploaded'}"
        )
        col1, col2 = st.columns(2)
        with col1:
            resume_file = st.file_uploader("Upload Resume (.txt)", type=["txt"], key="settings_resume")
            if resume_file:
                save_uploaded_file(resume_file, "user_profile/resume.txt")
                st.success("Resume updated!")
                st.rerun()
            if resume_ok and st.button("Preview Resume", use_container_width=True):
                st.text(st.session_state.resume_content[:2000])
        with col2:
            details_file = st.file_uploader("Upload Additional Details (.txt)", type=["txt"], key="settings_details")
            if details_file:
                save_uploaded_file(details_file, "user_profile/additional_details.txt")
                st.success("Additional details updated!")
                st.rerun()
            if details_ok and st.button("Preview Additional Details", use_container_width=True):
                st.text(st.session_state.details_content[:2000])
    with st.expander("API Keys", expanded=True):
        new_hf = st.text_input(
            "Hugging Face API Token",
            value=settings.get("hf_token", ""),
            type="password",
        )
        new_rapid = st.text_input(
            "Proxycurl / RapidAPI Key",
            value=settings.get("rapidapi_key", ""),
            type="password",
        )
        if st.button("Save API Keys", use_container_width=True):
            settings["hf_token"] = new_hf
            settings["rapidapi_key"] = new_rapid
            st.session_state.settings = settings
            save_settings(settings)
            st.success("API keys saved!")
    with st.expander("Gmail API", expanded=True):
        gmail_ok = bool(settings.get("gmail_creds"))
        st.markdown(
            f"**Gmail API:** {'| Connected' if gmail_ok else 'x Not configured'}"
        )
        creds_option = st.radio("Credentials source:", ["Upload credentials.json", "Paste JSON"])
        creds_json = settings.get("gmail_creds", "")
        new_creds = creds_json
        if creds_option == "Upload credentials.json":
            uploaded_creds = st.file_uploader("Upload credentials.json", type=["json"])
            if uploaded_creds:
                new_creds = uploaded_creds.getvalue().decode("utf-8")
                st.success("Credentials file loaded")
        else:
            new_creds = st.text_area("Paste the entire contents of your credentials.json file", value=creds_json, height=150)
        if st.button("Save & Test Gmail Connection", use_container_width=True):
            if new_creds:
                settings["gmail_creds"] = new_creds
                st.session_state.settings = settings
                save_settings(settings)
                try:
                    creds_dict = json.loads(new_creds)
                    result = gmail_sender.test_connection(creds_dict)
                    if result.get("success"):
                        st.success(
                            f"Gmail API connected as {result.get('email', '')}!"
                        )
                    else:
                        st.error(f"Connection failed: {result.get('error')}")
                except json.JSONDecodeError:
                    st.error("Invalid JSON in credentials")
            else:
                st.warning("Paste or upload credentials first")
    with st.expander("About"):
        st.markdown(f"**Sender Email:** dhruvg096@gmail.com")
        st.markdown("**App:** Aevom v1.0")
        if st.button("Clear All Caches", use_container_width=True):
            for f in ["cache/person_cache.json", "cache/company_cache.json", "gmail_token.json"]:
                if os.path.exists(f):
                    os.remove(f)
            st.success("Caches cleared!")


def render_generate_screen():
    st.header("Generate Email")
    mode = st.radio(
        "Input Mode",
        ["LinkedIn Post / Message", "Manual Entry"],
        horizontal=True,
        key="mode_selector",
    )
    st.session_state.mode = mode
    if mode == "LinkedIn Post / Message":
        render_linkedin_mode()
    else:
        render_manual_mode()


def render_linkedin_mode():
    pasted_text = st.text_area(
        "Paste LinkedIn post, X post, or any message here",
        height=200,
        key="pasted_text",
    )
    col_a, col_b = st.columns([1, 1])
    with col_a:
        analyze_btn = st.button("Analyze", use_container_width=True)
    with col_b:
        generate_btn = st.button("Generate Email", type="primary", use_container_width=True)

    entities = st.session_state.get("extracted_entities", {})

    if analyze_btn and pasted_text:
        with st.spinner("Analyzing text..."):
            entities = utils.extract_all_entities(pasted_text)
            entities["raw_text"] = pasted_text
            st.session_state.extracted_entities = entities

    if entities:
        st.subheader("Extracted Entities")
        cc1, cc2 = st.columns(2)
        with cc1:
            email = st.text_input(
                "Recipient Email",
                value=entities.get("primary_email") or "",
                key="edit_email",
            )
            linkedin = st.text_input(
                "LinkedIn URL",
                value=entities.get("linkedin_profile_url") or "",
                key="edit_linkedin",
            )
            company = st.text_input(
                "Hiring Company",
                value=entities.get("hiring_company") or "",
                key="edit_company",
            )
        with cc2:
            title = st.text_input(
                "Job Title",
                value=entities.get("job_title") or "",
                key="edit_title",
            )
            role_type = st.text_input(
                "Role Type",
                value=entities.get("role_type") or "",
                key="edit_role_type",
            )
            name = st.text_input(
                "Recruiter Name",
                value=entities.get("recruiter_name") or "",
                key="edit_name",
            )
        jd = st.text_area(
            "Job Description",
            value=entities.get("job_description") or "",
            height=100,
            key="edit_jd",
        )
        entities["confirmed_email"] = email
        entities["confirmed_linkedin"] = linkedin
        entities["confirmed_company"] = company
        entities["confirmed_title"] = title
        st.session_state.extracted_entities = entities

        api_key = (st.session_state.settings or {}).get("rapidapi_key", "")
        run_enrich = st.checkbox(
            "Run LinkedIn/Company Enrichment via Proxycurl",
            value=bool(api_key),
            disabled=not api_key,
        )
    else:
        run_enrich = False

    if generate_btn:
        if not pasted_text:
            st.warning("Please paste some text first.")
            return
        if not entities:
            entities = utils.extract_all_entities(pasted_text)
            entities["raw_text"] = pasted_text
            st.session_state.extracted_entities = entities

        entities = st.session_state.extracted_entities
        email = entities.get("confirmed_email") or entities.get("primary_email", "")
        linkedin_url = entities.get("confirmed_linkedin") or entities.get("linkedin_profile_url")

        if not email and not linkedin_url:
            st.warning("No email or LinkedIn URL found. Please provide at least one.")
            return

        person_profile = None
        company_profile = None
        posting_company = None
        hiring_company = None
        company_match = None
        confidence_score = None

        if run_enrich and api_key:
            if linkedin_url:
                url_type = utils.classify_linkedin_url(linkedin_url)
                if url_type == "profile":
                    with st.spinner("Fetching person profile..."):
                        try:
                            person_profile = enrichment.get_person_profile(linkedin_url, api_key)
                            if person_profile:
                                posting_company = person_profile.get("current_company")
                                entities["person_profile"] = person_profile
                        except Exception as e:
                            st.warning(f"Person profile enrichment failed: {e}")

            hiring_company = entities.get("confirmed_company") or entities.get("hiring_company")
            if not hiring_company and email:
                hiring_company = utils.company_name_from_email_domain(email)
            if not hiring_company and person_profile:
                hiring_company = posting_company

            if hiring_company and posting_company:
                confidence_score = utils.match_company_names(posting_company, hiring_company)
                company_match = confidence_score >= 60
            elif hiring_company:
                company_match = False
                confidence_score = 0

            if hiring_company:
                with st.spinner("Fetching company profile..."):
                    try:
                        if company_match and person_profile:
                            company_li_url = person_profile.get("current_company_linkedin_url")
                            if company_li_url:
                                company_profile = enrichment.get_company_profile(company_li_url, api_key)
                        else:
                            company_li_url = enrichment.resolve_company_url(hiring_company, api_key)
                            if company_li_url:
                                company_profile = enrichment.get_company_profile(company_li_url, api_key)
                        if company_profile:
                            entities["company_profile"] = company_profile
                    except Exception as e:
                        st.warning(f"Company enrichment failed: {e}")

        context = get_context_for_generation(entities=entities, mode="linkedin_post")
        result = generate_email(context)
        if result:
            result["context_used"] = []
            if st.session_state.resume_content:
                result["context_used"].append("Resume")
            if st.session_state.details_content:
                result["context_used"].append("Additional Details")
            if company_profile:
                result["context_used"].append("Hiring Company Data (Proxycurl)")
            if person_profile:
                result["context_used"].append("Recruiter Profile Data (Proxycurl)")
            if entities.get("job_description"):
                result["context_used"].append("Job Description")
            if pasted_text:
                result["context_used"].append("Post Content")
            st.session_state.current_output = result
            history_entry = {
                "recipient_email": email,
                "subject": result.get("primary_subject", ""),
                "body": result.get("email_body", ""),
                "followup_1": result.get("followup_1", ""),
                "followup_2": result.get("followup_2", ""),
                "followup_3": result.get("followup_3", ""),
                "sent": False,
                "sent_at": None,
                "mode": "linkedin_post",
                "hiring_company": hiring_company,
                "posting_user": (person_profile or {}).get("full_name", ""),
                "company_match": company_match,
                "confidence_score": confidence_score,
                "personalization_notes": result.get("personalization_notes", ""),
                "context_used": result.get("context_used", []),
                "flags": result.get("flags", []),
            }
            add_to_history(history_entry)
            st.rerun()

    if st.session_state.get("current_output"):
        render_email_output()


def render_manual_mode():
    with st.form("manual_form"):
        email = st.text_input("Recipient Email *", placeholder="recruiter@company.com")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Recipient Name", placeholder="Sarah Chen")
            title = st.text_input("Recipient Title", placeholder="ML Recruiter")
            company_name = st.text_input("Company Name", placeholder="Anthropic")
        with col2:
            job_title = st.text_input("Job Title / Role", placeholder="ML Engineer")
            company_desc = st.text_area("Company Description", height=80, placeholder="Tell us about the company...")
        jd = st.text_area("Job Description", height=120, placeholder="Paste job description here...")
        extra = st.text_area("Additional Context / Notes", height=80, placeholder="Any extra information...")
        submitted = st.form_submit_button("Generate Email", type="primary", use_container_width=True)

    if submitted:
        if not email:
            st.error("Recipient Email is required.")
            return
        manual = {
            "email": email,
            "name": name,
            "title": title or job_title,
            "company_name": company_name,
            "company_description": company_desc,
            "job_description": jd,
            "additional_context": extra,
        }
        context = get_context_for_generation(manual=manual, mode="manual_entry")
        result = generate_email(context)
        if result:
            result["context_used"] = []
            if st.session_state.resume_content:
                result["context_used"].append("Resume")
            if st.session_state.details_content:
                result["context_used"].append("Additional Details")
            if jd:
                result["context_used"].append("Job Description")
            if company_desc:
                result["context_used"].append("Company Description")
            st.session_state.current_output = result
            history_entry = {
                "recipient_email": email,
                "subject": result.get("primary_subject", ""),
                "body": result.get("email_body", ""),
                "followup_1": result.get("followup_1", ""),
                "followup_2": result.get("followup_2", ""),
                "followup_3": result.get("followup_3", ""),
                "sent": False,
                "sent_at": None,
                "mode": "manual",
                "hiring_company": company_name,
                "posting_user": "",
                "company_match": None,
                "confidence_score": None,
                "personalization_notes": result.get("personalization_notes", ""),
                "context_used": result.get("context_used", []),
                "flags": result.get("flags", []),
            }
            add_to_history(history_entry)
            st.rerun()

    if st.session_state.get("current_output"):
        render_email_output()


def render_email_output():
    output = st.session_state.current_output
    if not output:
        return

    if st.session_state.get("show_send_confirmation"):
        render_send_confirmation()
        return

    st.divider()
    st.markdown(
        "<h3 style='text-align:center; color:#00ffff;'>Generated Email</h3>",
        unsafe_allow_html=True,
    )

    entities = st.session_state.get("extracted_entities", {})
    if entities and any(entities.get(k) for k in ["primary_email", "confirmed_email", "hiring_company", "job_title", "recruiter_name", "linkedin_profile_url"]):
        with st.expander("Extracted Entities", expanded=False):
            email = entities.get("confirmed_email") or entities.get("primary_email", "")
            company = entities.get("confirmed_company") or entities.get("hiring_company", "")
            title = entities.get("confirmed_title") or entities.get("job_title", "")
            name = entities.get("recruiter_name", "")
            linkedin = entities.get("confirmed_linkedin") or entities.get("linkedin_profile_url", "")
            if email:
                st.markdown(f"**Email:** {email}")
            if company:
                st.markdown(f"**Company:** {company}")
            if title:
                st.markdown(f"**Title:** {title}")
            if name:
                st.markdown(f"**Name:** {name}")
            if linkedin:
                st.markdown(f"**LinkedIn:** {linkedin}")

    with st.expander("Personalization Transparency", expanded=True):
        if output.get("hiring_company"):
            st.markdown(f"**Hiring Company Detected:** {output.get('hiring_company', 'Not detected')}")
        if output.get("posting_user"):
            st.markdown(f"**Posting User:** {output.get('posting_user', 'N/A')}")
        match_status = output.get("company_match")
        if match_status is not None:
            st.markdown(
                f"**Posting Company == Hiring Company:** {'Yes' if match_status else 'No'}"
            )
        score = output.get("confidence_score")
        if score is not None:
            st.markdown(f"**Company Match Confidence Score:** {score}%")
        notes = output.get("personalization_notes", "")
        if notes:
            st.markdown(f"**Personalization Notes:** {notes}")
        ctx_used = output.get("context_used", [])
        if ctx_used:
            st.markdown("**Context Used:**")
            for item in ctx_used:
                st.markdown(f"| {item}")
        flags = output.get("flags", [])
        if flags:
            for flag in flags:
                st.markdown(f"<div class='alert-custom'>! {flag}</div>", unsafe_allow_html=True)
        forbidden = utils.check_forbidden_phrases(output.get("email_body", ""))
        if forbidden:
            for phrase in forbidden:
                st.markdown(f"<div class='alert-custom'>! Forbidden phrase detected: '{phrase}' — consider revising.</div>", unsafe_allow_html=True)

    st.subheader("Subject Lines")
    col_s1, col_s2 = st.columns([1, 4])
    with col_s1:
        selected_subject = st.radio(
            "Choose",
            ["Primary", "Variant A", "Variant B"],
            key="subject_choice",
            label_visibility="collapsed",
        )
    with col_s2:
        subjects = {
            "Primary": output.get("primary_subject", ""),
            "Variant A": output.get("subject_variant_a", ""),
            "Variant B": output.get("subject_variant_b", ""),
        }
        for label, subj in subjects.items():
            key = f"subject_{label}"
            edited = st.text_input(
                f"Subject {label}",
                value=subj,
                key=key,
                label_visibility="collapsed",
            )
            live_val = st.session_state.get(key, subj)
            subjects[label] = live_val
            char_count, warning = utils.check_subject_length(live_val)
            if warning:
                st.caption(warning)
            else:
                st.caption(f"{char_count} chars")

    st.subheader("Email Body")
    body_key = "edit_body"
    st.text_area(
        "Body",
        value=output.get("email_body", ""),
        height=250,
        key=body_key,
        label_visibility="collapsed",
    )
    live_body = st.session_state.get(body_key, output.get("email_body", ""))
    word_count = utils.count_words(live_body)
    st.caption(f"Word count: {word_count}")
    if word_count > 125:
        st.markdown(f"<div class='alert-custom'>Email body is {word_count} words — consider trimming for better response rates.</div>", unsafe_allow_html=True)

    send_followups = st.checkbox("Send follow-ups (1, 2, 3) after sending initial email", key="send_followups")

    with st.expander("Follow-Ups", expanded=send_followups):
        fu1 = st.text_area(
            "Follow-Up 1 (Day 3-4)", value=output.get("followup_1", ""), height=100
        )
        fu2 = st.text_area(
            "Follow-Up 2 (Day 7-8)", value=output.get("followup_2", ""), height=100
        )
        fu3 = st.text_area(
            "Follow-Up 3 (Day 12-14)", value=output.get("followup_3", ""), height=100
        )
        output["followup_1"] = fu1
        output["followup_2"] = fu2
        output["followup_3"] = fu3

    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        if st.button("Copy Email", use_container_width=True):
            selected = subjects.get(selected_subject, "")
            full_text = f"Subject: {selected}\n\n{live_body}"
            st.code(full_text, language="text")
            st.info("Copy the text above.")
    with col_b2:
        if st.button("Regenerate", use_container_width=True):
            st.session_state.current_output = None
            st.rerun()
    with col_b3:
        if st.button("Send Email", type="primary", use_container_width=True):
            st.session_state.show_send_confirmation = True
            st.rerun()


def render_send_confirmation():
    output = st.session_state.current_output

    body_key = "edit_body"
    live_body = st.session_state.get(body_key, output.get("email_body", "") if output else "")
    selected_subject = st.session_state.get("subject_choice", "Primary")
    live_subject = st.session_state.get(f"subject_{selected_subject}", "")
    if not live_subject:
        subjects_map = {"Primary": "primary_subject", "Variant A": "subject_variant_a", "Variant B": "subject_variant_b"}
        live_subject = output.get(subjects_map.get(selected_subject, "primary_subject"), "") if output else ""

    st.subheader("Pre-Send Confirmation")
    recipient_email = ""
    entry_id = ""
    for entry in reversed(st.session_state.email_history):
        if not entry.get("sent") and entry.get("body", "").strip() == (output.get("email_body", "") if output else "").strip():
            recipient_email = entry.get("recipient_email", "")
            entry_id = entry.get("id", "")
            break
    if not recipient_email:
        recipient_email = st.session_state.email_history[-1].get("recipient_email", "Unknown") if st.session_state.email_history else "Unknown"

    st.markdown(f"**To:** {recipient_email}")
    st.markdown("**From:** dhruvg096@gmail.com")
    st.markdown(f"**Subject:** {live_subject}")
    st.markdown("**Body:**")
    st.text(live_body)

    resume_path = "user_profile/resume.pdf"
    if os.path.exists(resume_path):
        st.markdown(f"**Attachment:** DhruvGoyal_res.pdf ({os.path.getsize(resume_path)//1024} KB)")

    st.divider()
    st.markdown("#### Pre-Send Checklist")
    check_result = utils.run_pre_send_checklist(live_subject, live_body, None)
    all_pass = True
    for check_name, passed in check_result.items():
        label = check_name.replace("_", " ").title()
        if passed:
            st.markdown(f"- | {label}")
        else:
            st.markdown(f"- x {label}")
            all_pass = False

    send_followups = st.session_state.get("send_followups", False)

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("> Confirm and Send", type="primary", use_container_width=True):
            settings = st.session_state.settings or {}
            creds_json = settings.get("gmail_creds", "")
            if not creds_json:
                st.error("Gmail API not configured. Go to Settings.")
                return
            try:
                creds_dict = json.loads(creds_json)
            except json.JSONDecodeError:
                st.error("Gmail credentials are not valid JSON. Re-paste the full credentials.json content in Settings.")
                return
            try:
                service = gmail_sender.authenticate(creds_dict)
                gmail_sender.send_message(service, recipient_email, live_subject, live_body, attachment_path=resume_path if os.path.exists(resume_path) else None)
                st.success("Email sent successfully!")
                if entry_id:
                    update_history_sent(entry_id)
                contact_tracker.add_contact(
                    company=st.session_state.current_output.get("hiring_company", ""),
                    contact_name="",
                    title="",
                    email=recipient_email,
                )
                st.session_state.show_send_confirmation = False
                st.rerun()
            except Exception as e:
                st.error(f"Failed to send: {e}")
    with col_c2:
        if st.button("x Cancel", use_container_width=True):
            st.session_state.show_send_confirmation = False
            st.rerun()


def render_history_screen():
    st.header("Email History")
    history = st.session_state.email_history
    if not history:
        st.info("No emails generated yet.")
        return
    filter_status = st.selectbox(
        "Filter by status", ["All", "Generated Only", "Sent"]
    )
    filtered = history
    if filter_status == "Generated Only":
        filtered = [e for e in history if not e.get("sent")]
    elif filter_status == "Sent":
        filtered = [e for e in history if e.get("sent")]
    for entry in reversed(filtered):
        sent_status = "| Sent" if entry.get("sent") else "o Generated"
        timestamp = entry.get("timestamp", "")[:19].replace("T", " ")
        preview = (entry.get("body") or "")[:80]
        with st.expander(
            f"[{sent_status}] {timestamp} — {entry.get('recipient_email', '?')} — {entry.get('subject', '?')}"
        ):
            st.markdown(f"**Subject:** {entry.get('subject', '')}")
            st.markdown(f"**Body:**")
            st.text(entry.get("body", ""))
            if entry.get("followup_1"):
                st.markdown(f"**Follow-Up 1:**")
                st.text(entry.get("followup_1", ""))
            if entry.get("followup_2"):
                st.markdown(f"**Follow-Up 2:**")
                st.text(entry.get("followup_2", ""))
            if entry.get("followup_3"):
                st.markdown(f"**Follow-Up 3:**")
                st.text(entry.get("followup_3", ""))
            notes = entry.get("personalization_notes", "")
            if notes:
                st.markdown(f"**Personalization:** {notes}")
            ctx = entry.get("context_used", [])
            if ctx:
                st.markdown(f"**Context Used:** {', '.join(ctx)}")
            flags = entry.get("flags", [])
            if flags:
                for f in flags:
                    st.warning(f)


def render_contact_tracker():
    st.header("Contact Tracker")
    contacts = contact_tracker.search_contacts("")
    search = st.text_input("Search contacts", placeholder="Search by company, name, email, or status...")
    if search:
        contacts = contact_tracker.search_contacts(search)
    due = contact_tracker.get_contacts_due_for_follow_up()
    if due:
        st.info(f"📬 {len(due)} contact(s) due for follow-up today!")
    if not contacts:
        st.info("No contacts tracked yet. Contacts are added when you send emails.")
        return
    for c in contacts:
        status_emoji = {
            "active": "🟢",
            "followed_up_1": "🔵",
            "followed_up_2": "🔵",
            "followed_up_3": "🔵",
            "responded": "🟣",
            "scheduled_call": "🟣",
            "rejected": "🔴",
            "closed": "⚪",
        }.get(c.get("status", ""), "⚪")
        with st.expander(
            f"{status_emoji} {c.get('company', '?')} — {c.get('contact_name', '?')} "
            f"[{c.get('follow_up_count', 0)} follow-ups]"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Company:** {c.get('company', '')}")
                st.markdown(f"**Contact:** {c.get('contact_name', '')}")
                st.markdown(f"**Title:** {c.get('title', '')}")
                st.markdown(f"**Email:** {c.get('email', '')}")
                st.markdown(f"**LinkedIn:** {c.get('linkedin_url', '')}")
            with col2:
                st.markdown(f"**Status:** {c.get('status', '')}")
                st.markdown(f"**Follow-ups Sent:** {c.get('follow_up_count', 0)}")
                st.markdown(f"**Last Contact:** {c.get('last_contact_date', '')}")
                next_date = c.get("next_follow_up_date") or "—"
                st.markdown(f"**Next Follow-up:** {next_date}")
                st.markdown(f"**Outcome:** {c.get('outcome', '')}")
            st.markdown(f"**Notes:** {c.get('notes', '')}")
            st.markdown(f"**Recommended:** {contact_tracker.get_recommended_next_action(c)}")
            action_cols = st.columns(5)
            cid = c.get("id")
            with action_cols[0]:
                if st.button("Advance Follow-up", key=f"adv_{cid}", use_container_width=True):
                    contact_tracker.advance_follow_up(cid)
                    st.rerun()
            with action_cols[1]:
                if st.button("Responded", key=f"resp_{cid}", use_container_width=True):
                    contact_tracker.mark_responded(cid)
                    st.rerun()
            with action_cols[2]:
                if st.button("Call Scheduled", key=f"call_{cid}", use_container_width=True):
                    contact_tracker.mark_scheduled_call(cid)
                    st.rerun()
            with action_cols[3]:
                if st.button("Rejected", key=f"rej_{cid}", use_container_width=True):
                    contact_tracker.mark_rejected(cid)
                    st.rerun()
            with action_cols[4]:
                if st.button("Close", key=f"close_{cid}", use_container_width=True):
                    contact_tracker.mark_closed(cid)
                    st.rerun()


def main():
    st.set_page_config(
        page_title="Aevom",
        page_icon="📧",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── Custom CSS ──
    st.markdown("""<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">""", unsafe_allow_html=True)
    st.markdown(
        """
    <style>
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }
    .material-icons, .material-symbols-outlined { font-family: 'Material Icons' !important; }

    #MainMenu, footer, header, div[data-testid="collapsedControl"] { display: none !important; }
    .stApp { background: #001a1a; }

    h1, h2, h3, h4, h5, h6 { color: #00ffff !important; }
    p, li, .stMarkdown, .stMarkdown strong { color: #00ffff !important; }
    label, .stTextInput label, .stTextArea label, .stSelectbox label,
    .stCheckbox label, .stRadio label, .stFileUploader label { color: #00ffff !important; }
    hr { border-color: #008080 !important; }
    a, a:visited { color: #00ffff !important; }
    a:hover { color: #00ccff !important; }
    .stCaption { color: #00aaaa !important; letter-spacing: 0.3px; }
    code { color: #00ffff !important; background: #002a2a !important; }

    /* ── Input boxes: kill default rounded border ── */
    .stTextInput > div, .stTextInput > div > div,
    .stTextArea > div, .stTextArea > div > div,
    .stSelectbox > div, .stSelectbox > div > div,
    .stFileUploader > div {
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        outline: none !important;
        background: transparent !important;
    }
    .stTextInput > div > div > input,
    .stTextArea textarea,
    .stSelectbox > div > div > div,
    .stFileUploader > div {
        background: #002222 !important;
        border: 1px solid #008080 !important;
        border-radius: 0 !important;
        color: #00ffff !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea textarea:focus {
        border-color: #00ffff !important;
    }
    .stTextInput > div > div > input::placeholder,
    .stTextArea textarea::placeholder {
        color: #006666 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: #002222;
        color: #00ffff;
        border: 1px solid #008080;
        border-radius: 0 !important;
        outline: none !important;
        box-shadow: none !important;
    }
    .stButton > button:hover { background: #003333; border-color: #00ffff; }
    .stButton > button:focus, .stButton > button:focus-visible { outline: none !important; box-shadow: none !important; }
    .stButton > button[kind="secondary"] { background: #002222; border: 1px solid #008080; }
    .stButton > button[kind="primary"] { background: #002222; border: 2px solid #00ffff; }

    .stForm [data-testid="baseButton-primary"] {
        background: #002222; border: 2px solid #00ffff; color: #00ffff;
        border-radius: 0 !important;
        outline: none !important; box-shadow: none !important;
    }
    .stForm [data-testid="baseButton-primary"]:hover { background: #003333; }

    /* ── Expanders ── */
    [data-testid="stExpander"] {
        background: #002a2a;
        border: 1px solid #008080;
        border-radius: 0 !important;
    }
    [data-testid="stExpander"]:hover { border-color: #00ffff; }
    [data-testid="stExpander"] details { background: #002a2a; }
    [data-testid="stExpander"] summary {
        color: #00ffff !important;
        font-weight: 600;
        background: #002a2a !important;
        border-radius: 0 !important;
    }
    [data-testid="stExpander"] summary:hover { background: #003333 !important; }

    /* ── Radio buttons ── */
    div[role="radiogroup"] label { color: #00ffff !important; }
    div[role="radiogroup"] input[type="radio"] { accent-color: #00ffff !important; }
    .stRadio div[role="radiogroup"] label > div:first-child { border-color: #00ffff !important; }
    .stRadio div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p { color: #00ffff !important; }

    /* ── Checkboxes ── */
    .stCheckbox div[data-testid="stMarkdownContainer"] p { color: #00ffff !important; }
    .stCheckbox input[type="checkbox"] { accent-color: #00ffff !important; }

    /* ── Alerts ── */
    div[data-testid="stAlert"] {
        border: 1px solid #008080 !important;
        background: #002a2a !important;
        border-radius: 0 !important;
    }
    div[data-testid="stAlert"] p { color: #00ffff !important; }
    .stInfo { border-color: #00ffff !important; }
    .stSuccess { border-color: #00cc88 !important; }
    .stWarning { background: #002a2a !important; border-color: #00aaaa !important; }
    .stError { background: #002a2a !important; border-color: #008888 !important; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background-color: #001a1a !important;
        border-right: 1px solid #008080;
    }
    section[data-testid="stSidebar"] .stMarkdown p { color: #00ffff !important; }
    section[data-testid="stSidebar"] .stMarkdown strong { color: #00ffff !important; }
    section[data-testid="stSidebar"] label { color: #00ffff !important; }
    section[data-testid="stSidebar"] .stRadio label { color: #00ffff !important; }
    section[data-testid="stSidebar"] hr { border-color: #008080 !important; }

    /* ── Misc ── */
    .stSpinner > div { border-color: #00ffff transparent transparent transparent !important; }
    [data-testid="column"] { gap: 0; }
    .stCode { border: 1px solid #008080; background: #002222; }
    .stCode code { color: #00ffff !important; }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #001111; }
    ::-webkit-scrollbar-thumb { background: #008080; }
    ::-webkit-scrollbar-thumb:hover { background: #00ffff; }

    .alert-custom {
        background: #002a2a;
        border: 1px solid #00aaaa;
        padding: 10px 14px;
        margin: 8px 0;
        color: #00ffff !important;
        font-size: 14px;
    }

    div[data-baseweb="select"] > div {
        background: #002222 !important;
        border-color: #008080 !important;
    }
    div[data-baseweb="select"] span { color: #00ffff !important; }
    ul[role="listbox"] { background: #002222 !important; }
    ul[role="listbox"] li { color: #00ffff !important; }
    ul[role="listbox"] li:hover { background: #003333 !important; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    init_session_state()
    if st.session_state.settings is None:
        st.session_state.settings = load_settings()
    load_profile_files()
    load_email_history()

    st.markdown(
        "<div style='text-align:center;'>"
        "<h1 style='color:#00ffff; font-weight:800; letter-spacing:-1px; font-size:3.5rem; margin-bottom:0; "
        "text-shadow:0 0 20px rgba(0,255,255,0.4),0 0 60px rgba(0,255,255,0.15);'>Aevom</h1>"
        "<hr style='border-color:#008080; width:60px; margin:12px auto; opacity:0.6;'>"
        "<p style='color:#00ffff; font-size:14px; letter-spacing:2px; margin:8px 0; text-transform:uppercase; font-weight:500;'>Cold email agent</p>"
        "<hr style='border-color:#008080; width:60px; margin:12px auto; opacity:0.6;'>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.divider()

        page = st.radio(
            "Go to",
            SIDEBAR_OPTIONS,
            index=SIDEBAR_OPTIONS.index(st.session_state.page),
            key="nav",
            label_visibility="collapsed",
        )
        st.session_state.page = page
        st.divider()
        st.markdown("**Status**")
        resume_ok = os.path.exists("user_profile/resume.txt")
        details_ok = os.path.exists("user_profile/additional_details.txt")
        hf_ok = bool((st.session_state.settings or {}).get("hf_token"))
        rapid_ok = bool((st.session_state.settings or {}).get("rapidapi_key"))
        gmail_ok = bool((st.session_state.settings or {}).get("gmail_creds"))
        st.markdown(f"{'|' if resume_ok else 'x'} Resume")
        st.markdown(f"{'|' if details_ok else 'x'} Details")
        st.markdown(f"{'|' if hf_ok else 'x'} HF Token")
        st.markdown(f"{'|' if rapid_ok else 'x'} RapidAPI")
        st.markdown(f"{'|' if gmail_ok else 'x'} Gmail API")

    page = st.session_state.page
    if page == "Generate Email":
        render_generate_screen()
    elif page == "Contact Tracker":
        render_contact_tracker()
    elif page == "Email History":
        render_history_screen()
    elif page == "Settings":
        render_settings_screen()


if __name__ == "__main__":
    main()
