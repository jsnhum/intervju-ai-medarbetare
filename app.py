import json
import time
import streamlit as st
import anthropic
import gspread
from google.oauth2.service_account import Credentials

# ── Constants ────────────────────────────────────────────────────────────────

MODEL = "claude-haiku-4-5-20251001"
DONE_TAG = "[INTERVIEW_DONE]"

# Silent kickoff message — never stored or shown, just starts the API conversation
KICKOFF = {
    "sv": "Starta intervjun.",
    "en": "Start the interview.",
}

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional researcher conducting a semi-structured research interview with a colleague at the Department of Cultural Studies at Linnaeus University in Sweden. Your role is to elicit thoughtful, reflective responses about the participant's relationship with AI in their academic work. Conduct yourself with the measured, attentive tone appropriate to an academic research context.

**Language**
Conduct the entire interview in {language}. Do not switch languages under any circumstances.

**Participant context**
{demographics}
Use this information to orient the conversation without being mechanical about it. Let it shape your opening question and inform which angles you pursue, but do not refer to it explicitly or make the participant feel profiled.

- Work distribution: weight the conversation accordingly — research practices and epistemological questions for researchers; pedagogy, student use, and classroom implications for teachers.
- Subject area: treat as a general backdrop that may inform which concerns feel salient, but do not narrow to discipline-specific detail.
- AI usage frequency: if they use AI daily, you can assume familiarity; if rarely or never, open more gently and do not presuppose experience.
- AI tools used: gives you a sense of where their experience lies; you may reference these types of tools when relevant but avoid making the interview feel like a product review.
- Self-reported attitude: treat as a starting orientation only. Someone who says "mostly negative" may still have nuanced or positive experiences worth exploring; someone "mostly positive" may harbour real concerns. Follow what the conversation actually reveals.

If no information was provided, proceed without assumptions.

**Conduct and style**
- Maintain a professional, respectful tone throughout — engaged and attentive, but not overly familiar
- When something substantive arises, follow it with a considered follow-up question before moving on; pursue threads, not just topics
- Let the conversation develop in the direction the participant takes it; do not redirect prematurely
- Treat ambivalence, complexity, and uncertainty as substantively interesting — acknowledge and explore them rather than moving past them
- Do not evaluate, validate, or express personal opinions about what the participant shares
- Vary your question types: open questions, follow-up questions, clarifying questions
- Keep your turns concise and focused — ask one question at a time

**Off-topic or disruptive responses**
If the participant attempts to redirect the conversation away from the interview, responds in a non-serious manner, or tries to engage you on matters unrelated to this interview, do not engage with the off-topic content. Instead, respond with exactly the following phrase on its own line:

Sorry Dave. I cannot do that.

Then, on the next line, restate your most recent question or the point you were exploring, and continue the interview.

**Themes to explore**
Cover these four themes organically, in whatever order feels natural given how the conversation develops. Follow threads where they lead. Return to uncovered themes when there is a natural opening — do not interrupt a substantive exchange in order to move through a checklist.

1. **Current use of AI**
   How do they use AI in their research, teaching, or administration? How has this changed over time? Do they make distinctions between different contexts or tasks?

2. **Attitudes**
   What has their experience been — what has worked, what has not? How do they account for their views? What do they observe among colleagues?

3. **Hopes**
   What possibilities do they see for AI in cultural studies research and teaching? What would they want AI to help with, now or in the future?

4. **Concerns and reservations**
   What gives them pause? This may include epistemological concerns (source criticism, authorship, interpretation, the nature of knowledge claims), concerns about students, about the discipline, about their own role, or broader institutional and societal questions.

**Opening the interview**
Begin with a measured, open question that invites the participant to engage with the topic on their own terms — not a direct question about any specific theme.

**Time limit**
{time_instruction}

**Closing the interview**
When all four themes have been sufficiently explored and the conversation feels naturally complete, close the interview professionally and thank the participant for their time. At the very end of your closing message, on a new line, include the tag [INTERVIEW_DONE]. This tag will not be shown to the participant."""


# ── Internationalisation ──────────────────────────────────────────────────────

STRINGS = {
    "sv": {
        "page_title": "AI i kulturvetenskaplig forskning och undervisning",
        "header_title": "AI i kulturvetenskaplig forskning och undervisning",
        "header_sub": "Institutionen för kulturvetenskap, Linnéuniversitetet · Anonymt deltagande",
        "steps": ["Språk", "Information", "Om dig", "Intervju", "Klar"],
        "info_title": "## Information om studien",
        "info_what_title": "Vad handlar studien om?",
        "info_what": (
            "Den här studien undersöker hur medarbetare vid Institutionen för kulturvetenskap "
            "vid Linnéuniversitetet använder och ser på AI – i forskning, undervisning och "
            "administration. Dina erfarenheter och reflektioner bidrar till att förstå hur AI "
            "förändrar akademiskt arbete inom humanistiska och samhällsvetenskapliga ämnen."
        ),
        "info_anon_title": "Anonymitet",
        "info_anon": (
            "Deltagandet är helt anonymt. Inga namn eller kontaktuppgifter samlas in. "
            "Ingen information kan kopplas till dig som person."
        ),
        "info_sensitive_title": "Känsliga uppgifter",
        "info_sensitive": (
            "Dela inte känsliga personuppgifter om dig själv eller om kollegor under intervjun."
        ),
        "info_voluntary_title": "Tid och frivillighet",
        "info_voluntary": (
            "Intervjun är beräknad till cirka 15 minuter, men det är ingen hård gräns. "
            "Du kan avbryta när som helst utan att ange skäl – om du avbryter sparas ingenting. "
            "När 15 minuter har gått kommer intervjuaren att uppmärksamma dig på detta och fråga "
            "om du vill fortsätta eller avsluta. Du bestämmer helt själv. "
            "Om du vill bidra med de svar du hunnit ge utan att slutföra intervjun kan du säga "
            "det i chatten – då kan du skicka in ändå."
        ),
        "accept": "Jag förstår och vill delta",
        "decline": "Nej tack",
        "demo_title": "## Lite om dig",
        "demo_intro": "Alla fält är frivilliga – lämna dem på standardvalet om du föredrar det.",
        "demo_subject_label": "Ämnesområde",
        "demo_subject_options": [
            "Vill inte ange", "Arkeologi", "Biblioteks- och informationsvetenskap",
            "Geografi", "Historia", "Religionsvetenskap", "Annat",
        ],
        "demo_subject_other_label": "Ange ämnesområde",
        "demo_balance_label": "Ungefärlig fördelning av din tjänst",
        "demo_balance_options": [
            "Vill inte ange",
            "Mestadels forskning",
            "Mestadels undervisning",
            "Ungefär lika delar forskning och undervisning",
            "Mestadels administration",
        ],
        "demo_frequency_label": "Hur ofta använder du AI i ditt arbete?",
        "demo_frequency_options": [
            "Vill inte ange", "Dagligen", "Några gånger i veckan",
            "Några gånger i månaden", "Sällan eller aldrig",
        ],
        "demo_systems_label": "Vilka typer av AI-verktyg använder du? (välj alla som stämmer)",
        "demo_systems_options": [
            "Chattbotar (t.ex. ChatGPT, Claude, Gemini)",
            "AI-verktyg för skrivande/redigering (t.ex. Copilot, Grammarly)",
            "Bild- eller mediegenerering",
            "AI-assisterad sökning",
            "Annat",
        ],
        "demo_attitude_label": "Hur skulle du övergripande beskriva din inställning till AI?",
        "demo_attitude_options": [
            "Vill inte ange", "Mestadels positiv", "Varken eller", "Mestadels negativ",
        ],
        "start_interview": "Starta intervjun",
        "interview_title": "## Intervju",
        "abort": "Avbryt (sparas inte)",
        "submit_early": "Avsluta och skicka in",
        "interview_done_msg": "Intervjun är klar! Tryck på knappen nedan för att skicka in dina svar.",
        "submit": "Skicka in mina svar",
        "chat_placeholder": "Skriv ditt svar här …",
        "aborted_title": "## Intervjun avbröts",
        "aborted_msg": "Dina svar har inte sparats.",
        "back_to_start": "Tillbaka till start",
        "declined_title": "## Tack ändå!",
        "declined_msg": "Det är helt okej. Ha en bra dag!",
        "thankyou_title": "## Tack för din medverkan!",
        "thankyou_msg": (
            "Dina svar har sparats och bidrar till forskning om AI i akademin. "
            "Vi uppskattar din tid och dina reflektioner."
        ),
        "save_error": "Kunde inte spara till Google Sheets: ",
    },
    "en": {
        "page_title": "AI in Cultural Studies Research and Teaching",
        "header_title": "AI in Cultural Studies Research and Teaching",
        "header_sub": "Department of Cultural Studies, Linnaeus University · Anonymous participation",
        "steps": ["Language", "Information", "About you", "Interview", "Done"],
        "info_title": "## About this study",
        "info_what_title": "What is this study about?",
        "info_what": (
            "This study explores how staff at the Department of Cultural Studies at Linnaeus "
            "University use and think about AI — in research, teaching, and administration. "
            "Your experiences and reflections contribute to understanding how AI is changing "
            "academic work in the humanities and social sciences."
        ),
        "info_anon_title": "Anonymity",
        "info_anon": (
            "Participation is fully anonymous. No names or contact details are collected. "
            "No information can be linked to you as an individual."
        ),
        "info_sensitive_title": "Sensitive information",
        "info_sensitive": (
            "Please do not share sensitive personal information about yourself or "
            "colleagues during the interview."
        ),
        "info_voluntary_title": "Time and voluntary participation",
        "info_voluntary": (
            "The interview is estimated to take approximately 15 minutes, but this is not a hard limit. "
            "You may stop at any time without giving a reason — if you stop, nothing is saved. "
            "When 15 minutes have passed, the interviewer will let you know and ask whether you "
            "would like to continue or wrap up. The choice is entirely yours. "
            "If you wish to submit the responses you have given without completing the interview, "
            "you can say so in the chat and submit anyway."
        ),
        "accept": "I understand and wish to participate",
        "decline": "No thank you",
        "demo_title": "## About you",
        "demo_intro": "All fields are optional — leave them at the default if you prefer.",
        "demo_subject_label": "Subject area",
        "demo_subject_options": [
            "Prefer not to say", "Archaeology", "Library and Information Science",
            "Geography", "History", "Religious Studies", "Other",
        ],
        "demo_subject_other_label": "Please specify subject area",
        "demo_balance_label": "Approximate distribution of your position",
        "demo_balance_options": [
            "Prefer not to say",
            "Mostly research",
            "Mostly teaching",
            "Roughly equal research and teaching",
            "Mostly administration",
        ],
        "demo_frequency_label": "How often do you use AI in your work?",
        "demo_frequency_options": [
            "Prefer not to say", "Daily", "A few times a week",
            "A few times a month", "Rarely or never",
        ],
        "demo_systems_label": "Which types of AI tools do you use? (select all that apply)",
        "demo_systems_options": [
            "Chatbots (e.g. ChatGPT, Claude, Gemini)",
            "AI writing/editing tools (e.g. Copilot, Grammarly)",
            "Image or media generation",
            "AI-assisted search",
            "Other",
        ],
        "demo_attitude_label": "How would you broadly describe your attitude toward AI?",
        "demo_attitude_options": [
            "Prefer not to say", "Mostly positive", "Neither positive nor negative", "Mostly negative",
        ],
        "start_interview": "Start interview",
        "interview_title": "## Interview",
        "abort": "Abort (nothing saved)",
        "submit_early": "Finish and submit",
        "interview_done_msg": "The interview is complete! Press the button below to submit your responses.",
        "submit": "Submit my responses",
        "chat_placeholder": "Type your response here …",
        "aborted_title": "## Interview aborted",
        "aborted_msg": "Your responses have not been saved.",
        "back_to_start": "Back to start",
        "declined_title": "## Thank you anyway!",
        "declined_msg": "That's perfectly fine. Have a great day!",
        "thankyou_title": "## Thank you for your participation!",
        "thankyou_msg": (
            "Your responses have been saved and contribute to research on AI in academia. "
            "We appreciate your time and reflections."
        ),
        "save_error": "Could not save to Google Sheets: ",
    },
}


def t(key: str) -> str:
    """Return the UI string for the current language."""
    lang = st.session_state.get("language", "sv")
    return STRINGS[lang][key]


# ── Google Sheets ─────────────────────────────────────────────────────────────

def get_sheet():
    creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(dict(creds_dict), scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(st.secrets["GOOGLE_SHEET_NAME"]).sheet1


def save_to_sheets(demographics: dict, messages: list, start_time: float, language: str):
    try:
        sheet = get_sheet()
        duration = int(time.time() - start_time)
        user_msgs = sum(1 for m in messages if m["role"] == "user")
        row = [
            time.strftime("%Y-%m-%d %H:%M:%S"),
            language,
            duration,
            user_msgs,
            demographics.get("subject", ""),
            demographics.get("balance", ""),
            demographics.get("frequency", ""),
            ", ".join(demographics.get("systems", [])),
            demographics.get("attitude", ""),
            json.dumps(messages, ensure_ascii=False),
        ]
        sheet.append_row(row)
    except Exception as e:
        st.error(t("save_error") + str(e))


# ── Demographics helpers ──────────────────────────────────────────────────────

_SKIP = {"Vill inte ange", "Prefer not to say", ""}


def build_demographics_section(demo: dict) -> str:
    lines = []
    if (v := demo.get("subject", "")) and v not in _SKIP:
        lines.append(f"- Subject area: {v}")
    if (v := demo.get("balance", "")) and v not in _SKIP:
        lines.append(f"- Work distribution: {v}")
    if (v := demo.get("frequency", "")) and v not in _SKIP:
        lines.append(f"- AI usage frequency: {v}")
    if systems := demo.get("systems", []):
        lines.append(f"- AI tools used: {', '.join(systems)}")
    if (v := demo.get("attitude", "")) and v not in _SKIP:
        lines.append(f"- Self-reported attitude toward AI: {v}")
    if not lines:
        return "No background information was provided."
    return "The participant provided the following background information:\n" + "\n".join(lines)


# ── Claude streaming ──────────────────────────────────────────────────────────

INTERVIEW_HALFWAY_SECONDS = 7 * 60 + 30   # 7.5 minutes
INTERVIEW_WARNING_SECONDS = 15 * 60        # 15 minutes

TIME_INSTRUCTION_NORMAL = {
    "sv": (
        "Intervjun är planerad till cirka 15 minuter. "
        "Fördela uppmärksamheten någorlunda jämnt över de fyra temana — "
        "inget enskilt tema bör dominera mer än en fjärdedel av samtalet."
    ),
    "en": (
        "The interview is planned to last approximately 15 minutes. "
        "Distribute attention reasonably across the four themes — "
        "no single theme should occupy more than a quarter of the conversation."
    ),
}

TIME_INSTRUCTION_HALFWAY = {
    "sv": (
        "Ungefär hälften av den planerade intervjutiden har nu gått. "
        "Gör en intern bedömning av vilka teman som hittills behandlats tillräckligt "
        "och vilka som ännu inte berörts — och börja styra samtalet mot de teman "
        "som saknas, utan att avbryta trådar abrupt."
    ),
    "en": (
        "Approximately half the planned interview time has now passed. "
        "Internally assess which themes have been sufficiently covered and which "
        "have not yet been addressed — and begin steering toward the missing ones, "
        "without abruptly cutting off current threads."
    ),
}

TIME_INSTRUCTION_WARNING = {
    "sv": (
        "Den planerade intervjutiden på 15 minuter har nu passerats. "
        "Meddela deltagaren på ett naturligt sätt att den planerade tiden är slut, "
        "och fråga om de vill fortsätta ett litet tag till eller om de föredrar att avsluta. "
        "Anpassa dig till deras svar."
    ),
    "en": (
        "The planned 15-minute interview time has now passed. "
        "Let the participant know naturally that the planned time is up, "
        "and ask whether they would like to continue for a little longer or prefer to wrap up. "
        "Follow their lead."
    ),
}

TIME_INSTRUCTION_EXTENDED = {
    "sv": (
        "Deltagaren har valt att fortsätta efter den planerade tiden. "
        "Fortsätt intervjun naturligt och avsluta när samtalet känns färdigt."
    ),
    "en": (
        "The participant has chosen to continue beyond the planned time. "
        "Continue the interview naturally and close when the conversation feels complete."
    ),
}


def stream_claude(messages: list, demographics: dict):
    """Stream Claude's response. Always prepends a silent kickoff so messages start with 'user'."""
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    lang = st.session_state.get("language", "sv")
    elapsed = time.time() - st.session_state.get("start_time", time.time())
    warning_given = st.session_state.get("time_warning_given", False)

    if elapsed > INTERVIEW_WARNING_SECONDS and not warning_given:
        time_instruction = TIME_INSTRUCTION_WARNING[lang]
        st.session_state.time_warning_given = True
    elif warning_given:
        time_instruction = TIME_INSTRUCTION_EXTENDED[lang]
    elif elapsed > INTERVIEW_HALFWAY_SECONDS:
        time_instruction = TIME_INSTRUCTION_HALFWAY[lang]
    else:
        time_instruction = TIME_INSTRUCTION_NORMAL[lang]
    system = SYSTEM_PROMPT.format(
        language="Swedish" if lang == "sv" else "English",
        demographics=build_demographics_section(demographics),
        time_instruction=time_instruction,
    )
    kickoff = {"role": "user", "content": KICKOFF[lang]}
    api_messages = [kickoff] + messages
    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=api_messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


# ── Styling ───────────────────────────────────────────────────────────────────

def apply_styles():
    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility: hidden; }
        .stApp { background-color: #F5F4F0; }
        .block-container {
            max-width: 700px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }
        .app-header {
            border-bottom: 2px solid #4A5568;
            padding-bottom: 0.6rem;
            margin-bottom: 1.8rem;
        }
        .app-header h1 {
            font-size: 1.1rem;
            font-weight: 600;
            color: #4A5568;
            letter-spacing: 0.02em;
            margin: 0;
        }
        .app-header p {
            font-size: 0.78rem;
            color: #888;
            margin: 0.15rem 0 0 0;
        }
        .steps {
            display: flex;
            gap: 0;
            margin-bottom: 1.8rem;
            border-radius: 6px;
            overflow: hidden;
            border: 1px solid #ddd;
        }
        .step {
            flex: 1;
            text-align: center;
            padding: 0.45rem 0.2rem;
            font-size: 0.72rem;
            color: #aaa;
            background: #fff;
            border-right: 1px solid #ddd;
        }
        .step:last-child { border-right: none; }
        .step.done { background: #eaecf0; color: #4A5568; }
        .step.active { background: #4A5568; color: #fff; font-weight: 600; }
        h2 { color: #222; margin-bottom: 1rem; }
        .card {
            background: #fff;
            border: 1px solid #e0ddd8;
            border-radius: 8px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.2rem;
        }
        .card h3 { margin-top: 0; color: #4A5568; font-size: 0.95rem; }
        .card p  { margin: 0.3rem 0 0 0; color: #444; font-size: 0.9rem; line-height: 1.5; }
        </style>
        """,
        unsafe_allow_html=True,
    )


STEP_PAGE = {
    "language": 0, "info": 1, "demographics": 2,
    "interview": 3, "thank_you": 4,
    "declined": 1, "aborted": 3,
}


def render_header(page: str):
    lang = st.session_state.get("language", "sv")
    step_labels = STRINGS[lang]["steps"]
    step_idx = STEP_PAGE.get(page, 0)
    steps_html = "".join(
        f'<div class="step {"active" if i == step_idx else "done" if i < step_idx else ""}">'
        f"{label}</div>"
        for i, label in enumerate(step_labels)
    )
    st.markdown(
        f"""
        <div class="app-header">
          <h1>{STRINGS[lang]["header_title"]}</h1>
          <p>{STRINGS[lang]["header_sub"]}</p>
        </div>
        <div class="steps">{steps_html}</div>
        """,
        unsafe_allow_html=True,
    )


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_language():
    st.markdown("## Välj språk &nbsp;/&nbsp; Choose language")
    lang = st.radio(
        "Välj språk / Select language",
        options=["sv", "en"],
        format_func=lambda x: "Svenska / Swedish" if x == "sv" else "English / Engelska",
        horizontal=True,
    )
    if st.button("Fortsätt / Continue", type="primary"):
        st.session_state.language = lang
        st.session_state.page = "info"
        st.rerun()


def page_info():
    st.markdown(t("info_title"))
    st.markdown(
        f"""
        <div class="card">
          <h3>{t("info_what_title")}</h3>
          <p>{t("info_what")}</p>
        </div>
        <div class="card">
          <h3>{t("info_anon_title")}</h3>
          <p>{t("info_anon")}</p>
        </div>
        <div class="card">
          <h3>{t("info_sensitive_title")}</h3>
          <p>{t("info_sensitive")}</p>
        </div>
        <div class="card">
          <h3>{t("info_voluntary_title")}</h3>
          <p>{t("info_voluntary")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("accept"), type="primary", use_container_width=True):
            st.session_state.page = "demographics"
            st.rerun()
    with col2:
        if st.button(t("decline"), use_container_width=True):
            st.session_state.page = "declined"
            st.rerun()


def page_declined():
    st.markdown(t("declined_title"))
    st.write(t("declined_msg"))


def page_demographics():
    st.markdown(t("demo_title"))
    st.write(t("demo_intro"))

    subject_options = t("demo_subject_options")
    subject = st.selectbox(t("demo_subject_label"), subject_options)
    subject_other = ""
    if subject == subject_options[-1]:  # "Annat" / "Other"
        subject_other = st.text_input(t("demo_subject_other_label"))

    balance = st.selectbox(t("demo_balance_label"), t("demo_balance_options"))
    frequency = st.selectbox(t("demo_frequency_label"), t("demo_frequency_options"))
    systems = st.multiselect(t("demo_systems_label"), t("demo_systems_options"))
    attitude = st.selectbox(t("demo_attitude_label"), t("demo_attitude_options"))

    if st.button(t("start_interview"), type="primary"):
        final_subject = (
            subject_other.strip()
            if subject == subject_options[-1] and subject_other.strip()
            else subject
        )
        st.session_state.demographics = {
            "subject": final_subject,
            "balance": balance,
            "frequency": frequency,
            "systems": systems,
            "attitude": attitude,
        }
        st.session_state.messages = []
        st.session_state.start_time = time.time()
        st.session_state.interview_done = False
        st.session_state.time_warning_given = False
        st.session_state.page = "interview"
        st.rerun()


def page_interview():
    st.markdown(t("interview_title"))

    col_abort, col_early = st.columns(2)
    with col_abort:
        if st.button(t("abort"), type="secondary", use_container_width=True):
            st.session_state.page = "aborted"
            st.rerun()
    with col_early:
        if st.session_state.get("messages") and not st.session_state.get("interview_done"):
            if st.button(t("submit_early"), use_container_width=True):
                save_to_sheets(
                    st.session_state.demographics,
                    st.session_state.messages,
                    st.session_state.start_time,
                    st.session_state.get("language", "sv"),
                )
                st.session_state.page = "thank_you"
                st.rerun()

    messages: list = st.session_state.messages
    demographics: dict = st.session_state.demographics
    chat_area = st.container(height=500, border=False)

    with chat_area:
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if st.session_state.get("interview_done"):
        with chat_area:
            st.success(t("interview_done_msg"))
        if st.button(t("submit"), type="primary"):
            save_to_sheets(
                demographics,
                messages,
                st.session_state.start_time,
                st.session_state.get("language", "sv"),
            )
            st.session_state.page = "thank_you"
            st.rerun()
        return

    # First turn: Claude opens the conversation (messages is empty, kickoff prepended in stream_claude)
    if not messages:
        with chat_area:
            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""
                for chunk in stream_claude([], demographics):
                    full_response += chunk
                    placeholder.markdown(full_response + "▌")
                clean = full_response.replace(DONE_TAG, "").strip()
                placeholder.markdown(clean)
        messages.append({"role": "assistant", "content": clean})
        st.session_state.messages = messages
        if DONE_TAG in full_response:
            st.session_state.interview_done = True
        st.rerun()
        return

    user_input = st.chat_input(t("chat_placeholder"))
    if user_input:
        messages.append({"role": "user", "content": user_input})
        with chat_area:
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""
                for chunk in stream_claude(messages, demographics):
                    full_response += chunk
                    placeholder.markdown(full_response + "▌")
                clean = full_response.replace(DONE_TAG, "").strip()
                placeholder.markdown(clean)
        messages.append({"role": "assistant", "content": clean})
        st.session_state.messages = messages
        if DONE_TAG in full_response:
            st.session_state.interview_done = True
        st.rerun()


def page_aborted():
    st.markdown(t("aborted_title"))
    st.info(t("aborted_msg"))
    if st.button(t("back_to_start")):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def page_thank_you():
    st.markdown(t("thankyou_title"))
    st.write(t("thankyou_msg"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="AI i kulturvetenskaplig forskning och undervisning",
        page_icon="🎓",
        layout="centered",
    )

    if "page" not in st.session_state:
        st.session_state.page = "language"

    apply_styles()
    render_header(st.session_state.page)

    page = st.session_state.page
    if page == "language":
        page_language()
    elif page == "info":
        page_info()
    elif page == "declined":
        page_declined()
    elif page == "demographics":
        page_demographics()
    elif page == "interview":
        page_interview()
    elif page == "aborted":
        page_aborted()
    elif page == "thank_you":
        page_thank_you()


if __name__ == "__main__":
    main()
