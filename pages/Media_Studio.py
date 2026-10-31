import json
from pathlib import Path
from io import BytesIO

import streamlit as st
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

st.set_page_config(
    page_title="Media Studio | The Case Study Engine",
    page_icon="🎨",
    layout="wide"
)

ROOT = Path(__file__).resolve().parent.parent
WRITER_FILE = ROOT / "outputs" / "case_study" / "writer_output.json"

NAVY = RGBColor(13, 22, 39)
PANEL = RGBColor(24, 38, 60)
CYAN = RGBColor(68, 203, 218)
WHITE = RGBColor(245, 248, 252)
MUTED = RGBColor(174, 190, 208)
AMBER = RGBColor(255, 190, 92)
RED = RGBColor(235, 105, 105)


def load_writer():
    if not WRITER_FILE.exists():
        return {}
    try:
        with WRITER_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def clean(value, fallback="Not established in available records."):
    if value is None or value == "":
        return fallback
    if isinstance(value, list):
        return "\n".join(f"• {x}" for x in value) if value else fallback
    return str(value)


def add_text(slide, x, y, w, h, text, size=18, color=WHITE,
             bold=False, font="Aptos", align=None):
    box = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.02)
    tf.margin_right = Inches(0.02)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    if align is not None:
        p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_rect(slide, x, y, w, h, color, radius=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        shape_type, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_base(prs, number, section, draft=True):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY

    add_rect(slide, 0.55, 0.55, 0.12, 6.35, CYAN)
    add_text(slide, 0.85, 0.48, 7.2, 0.3,
             "THE CASE STUDY ENGINE  /  PROJECT DRISHTI",
             9, MUTED, True)
    add_text(slide, 0.85, 6.93, 5.5, 0.25,
             f"{section.upper()}  •  PREPARED FOR CLIENT REVIEW",
             8, MUTED, True)
    add_text(slide, 8.15, 6.91, 0.5, 0.25,
             f"{number:02d}/06", 9, CYAN, True, align=PP_ALIGN.RIGHT)

    if draft:
        add_rect(slide, 6.0, 0.45, 2.55, 0.34, RGBColor(75, 43, 45), True)
        add_text(slide, 6.08, 0.49, 2.4, 0.22,
                 "DRAFT • NOT APPROVED FOR SHARING",
                 7, RGBColor(255, 175, 175), True,
                 align=PP_ALIGN.CENTER)
    return slide


def build_carousel(title, audience, draft, project_label):
    prs = Presentation()
    prs.slide_width = Inches(8.7)
    prs.slide_height = Inches(7.3)

    problem = clean(draft.get("problem"))
    approach = clean(draft.get("approach"))
    implementation = clean(draft.get("implementation"))
    results = clean(draft.get("results_and_impact"))
    conclusion = clean(draft.get("conclusion"))
    limitations = clean(draft.get("limitations", []))
    objectives = clean(draft.get("objectives", []))

    # Slide 1 — Cover
    s = add_base(prs, 1, "Overview")
    add_text(s, 0.95, 1.55, 6.9, 0.5,
             "PROJECT STORY  /  CLIENT REVIEW EDITION",
             11, CYAN, True)
    add_text(s, 0.95, 2.2, 7.0, 1.7,
             title, 30, WHITE, True)
    add_text(s, 0.98, 4.35, 6.6, 0.9,
             f"A concise project narrative for {audience.lower()} stakeholders.",
             17, MUTED)
    add_rect(s, 0.98, 5.55, 5.7, 0.72, PANEL, True)
    add_text(s, 1.2, 5.72, 5.3, 0.35,
             "PRELIMINARY • FACTS AND PERMISSIONS REQUIRE REVIEW",
             10, AMBER, True)

    # Slide 2 — Challenge
    s = add_base(prs, 2, "The challenge")
    add_text(s, 0.98, 1.15, 7.0, 0.6, "01  /  THE CHALLENGE", 13, CYAN, True)
    add_text(s, 0.98, 1.9, 7.0, 0.8, "What needed to be addressed", 25, WHITE, True)
    add_rect(s, 0.98, 3.0, 6.95, 2.65, PANEL, True)
    add_text(s, 1.25, 3.28, 6.4, 2.1, problem, 16, WHITE)

    # Slide 3 — Approach
    s = add_base(prs, 3, "The approach")
    add_text(s, 0.98, 1.15, 7.0, 0.6, "02  /  THE APPROACH", 13, CYAN, True)
    add_text(s, 0.98, 1.9, 7.0, 0.8, "How the work was framed", 25, WHITE, True)
    add_rect(s, 0.98, 3.0, 6.95, 2.65, PANEL, True)
    add_text(s, 1.25, 3.28, 6.4, 2.1, approach, 16, WHITE)

    # Slide 4 — Project activity
    s = add_base(prs, 4, "Project activity")
    add_text(s, 0.98, 1.15, 7.0, 0.6, "03  /  PROJECT ACTIVITY", 13, CYAN, True)
    add_text(s, 0.98, 1.9, 7.0, 0.8, "What the available records show", 25, WHITE, True)
    add_rect(s, 0.98, 3.0, 6.95, 2.65, PANEL, True)
    add_text(s, 1.25, 3.28, 6.4, 2.1, implementation, 14, WHITE)

    # Slide 5 — Evidence / outcomes
    s = add_base(prs, 5, "Evidence and outcomes")
    add_text(s, 0.98, 1.15, 7.0, 0.6, "04  /  EVIDENCE & OUTCOMES", 13, CYAN, True)
    add_text(s, 0.98, 1.9, 7.0, 0.8, "What can be claimed today?", 25, WHITE, True)
    add_rect(s, 0.98, 3.0, 6.95, 2.65, PANEL, True)
    add_text(s, 1.25, 3.28, 6.4, 2.1, results, 14, WHITE)

    # Slide 6 — Next steps / approval
    s = add_base(prs, 6, "Review and next steps")
    add_text(s, 0.98, 1.15, 7.0, 0.6, "05  /  REVIEW & NEXT STEPS", 13, CYAN, True)
    add_text(s, 0.98, 1.9, 7.0, 0.8, "Before this story is shared", 25, WHITE, True)
    add_rect(s, 0.98, 3.0, 6.95, 2.65, PANEL, True)
    add_text(s, 1.25, 3.25, 6.4, 1.55, conclusion, 14, WHITE)
    add_text(s, 1.25, 4.95, 6.4, 0.55,
             "Required: verify claims • review exposure • approve exact copy and visuals",
             11, AMBER, True)

    output = BytesIO()
    prs.save(output)
    output.seek(0)
    return output.getvalue()


# -------------------- PAGE --------------------

st.title("Media Studio")
st.caption("Turn an audience-specific case-study draft into an editable, exportable carousel.")

writer = load_writer()
case_studies = writer.get("case_studies", {}) if isinstance(writer, dict) else {}

if not case_studies:
    st.error("Writer output not found. Run the Writer Agent first.")
    st.code("python agents/writer.py")
    st.stop()

st.info(
    "This creates an editable PowerPoint carousel. It is a review draft, "
    "not an approved client deliverable. The deck is labelled accordingly."
)

audience = st.selectbox("Choose the target audience", list(case_studies.keys()))
draft = case_studies[audience]

default_title = str(draft.get("title", "Project story"))
title = st.text_input("Carousel headline", value=default_title)
project_label = st.text_input("Project label", value="Project Drishti")

st.markdown("### Content preview")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Challenge**")
    st.write(clean(draft.get("problem")))
    st.markdown("**Approach**")
    st.write(clean(draft.get("approach")))
with c2:
    st.markdown("**Implementation**")
    st.write(clean(draft.get("implementation")))
    st.markdown("**Results and impact**")
    st.write(clean(draft.get("results_and_impact")))

st.markdown("### Export")
st.write("The carousel contains six editable 4:5-style presentation slides: cover, challenge, approach, project activity, evidence/outcomes, and review/next steps.")

if st.button("Generate editable carousel", type="primary", use_container_width=True):
    try:
        pptx_bytes = build_carousel(
            title=title,
            audience=audience,
            draft=draft,
            project_label=project_label
        )
        st.session_state["carousel_bytes"] = pptx_bytes
        st.session_state["carousel_name"] = audience.lower()
        st.success("Carousel generated. Review every slide before sharing.")
    except Exception as exc:
        st.error(f"Could not generate carousel: {exc}")

if st.session_state.get("carousel_bytes"):
    st.download_button(
        "Download editable PowerPoint carousel",
        data=st.session_state["carousel_bytes"],
        file_name=f"project_drishti_{st.session_state['carousel_name']}_carousel_DRAFT.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        use_container_width=True
    )

st.warning(
    "No unverified KPI values are added as achievements. The current source draft "
    "contains incomplete metrics and unreviewed claims. Do not send this deck to "
    "the client until the exact wording, identifying details, visuals and permissions "
    "have been reviewed and approved."
)
