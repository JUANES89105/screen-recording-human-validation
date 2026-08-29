from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Validación humana",
    layout="wide"
)


# ============================================================
# CONFIG
# ============================================================

BASE = Path("validation")

SAMPLE_FILE = BASE / "validation_sample.csv"
IMAGES_DIR = BASE / "images"

LOCAL_CREDS = Path(
    ".secrets/service_account.json"
)

CATEGORIES = [
    "GeoGebra",
    "Google",
    "Google (Mat)",
    "Juegos",
    "Otro sitio",
    "Quinan",
    "Screen Recorder",
    "Wikipedia",
    "YouTube",
]


# ============================================================
# CREDENTIALS
# ============================================================

def get_google_credentials():

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # --------------------------------------------------------
    # STREAMLIT CLOUD
    # --------------------------------------------------------

    try:
        if "gcp_service_account" in st.secrets:

            info = dict(
                st.secrets["gcp_service_account"]
            )

            return Credentials.from_service_account_info(
                info,
                scopes=scopes
            )

    except Exception:
        pass

    # --------------------------------------------------------
    # LOCAL
    # --------------------------------------------------------

    if LOCAL_CREDS.exists():

        return Credentials.from_service_account_file(
            LOCAL_CREDS,
            scopes=scopes
        )

    raise RuntimeError(
        "No se encontraron credenciales de Google."
    )


@st.cache_resource
def get_worksheet(evaluator_id):

    creds = get_google_credentials()

    gc = gspread.authorize(
        creds
    )

    spreadsheet_id = str(
        st.secrets["spreadsheet_id"]
    )

    spreadsheet = gc.open_by_key(
        spreadsheet_id
    )

    return spreadsheet.worksheet(
        str(evaluator_id)
    )


# ============================================================
# SAMPLE
# ============================================================

@st.cache_data
def load_sample():

    df = pd.read_csv(
        SAMPLE_FILE,
        dtype={"image_id": str}
    )

    return df


# ============================================================
# GOOGLE SHEETS
# ============================================================

def load_all_responses(evaluator_id):

    ws = get_worksheet(evaluator_id)

    records = ws.get_all_records()

    if not records:

        return pd.DataFrame(
            columns=[
                "evaluator_id",
                "image_id",
                "category",
                "timestamp",
            ]
        )

    return pd.DataFrame(
        records
    )


def load_evaluator_responses(
    evaluator_id
):

    df = load_all_responses(evaluator_id)

    if df.empty:
        return df

    return df[
        df["evaluator_id"]
        .astype(str)
        .eq(str(evaluator_id))
    ].copy()


def save_response(
    evaluator_id,
    image_id,
    category
):

    ws = get_worksheet(evaluator_id)

    values = ws.get_all_values()

    existing_row = None

    # --------------------------------------------------------
    # BUSCAR RESPUESTA PREVIA
    # --------------------------------------------------------

    for row_number, row in enumerate(
        values[1:],
        start=2
    ):

        if len(row) < 2:
            continue

        if (
            str(row[0]) == str(evaluator_id)
            and
            str(row[1]) == str(image_id)
        ):

            existing_row = row_number
            break

    timestamp = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    new_values = [[
        evaluator_id,
        image_id,
        category,
        timestamp,
    ]]

    # --------------------------------------------------------
    # ACTUALIZAR O INSERTAR
    # --------------------------------------------------------

    if existing_row is not None:

        ws.update(
            range_name=(
                f"A{existing_row}:D{existing_row}"
            ),
            values=new_values
        )

    else:

        ws.append_row(
            new_values[0],
            value_input_option="RAW"
        )


# ============================================================
# AUTHENTICATION BY URL
# ============================================================

params = st.query_params

evaluator_id = str(
    params.get(
        "evaluator",
        ""
    )
).strip()

provided_token = str(
    params.get(
        "token",
        ""
    )
).strip()


try:

    evaluator_tokens = dict(
        st.secrets[
            "evaluator_tokens"
        ]
    )

except Exception:

    evaluator_tokens = {}


expected_token = (
    evaluator_tokens.get(
        evaluator_id
    )
)


if (
    evaluator_id not in evaluator_tokens
    or not provided_token
    or provided_token != expected_token
):

    st.title(
        "Validación humana"
    )

    st.error(
        "El enlace de acceso no es válido."
    )

    st.stop()


# ============================================================
# LOAD SAMPLE
# ============================================================

sample = load_sample()

n_total = len(sample)


# ============================================================
# TITLE
# ============================================================

st.title(
    "Validación humana de capturas"
)

st.write(
    """
    Observe cada captura y seleccione la categoría
    que mejor representa el sitio o plataforma
    visualizada.
    """
)

st.caption(
    f"Evaluador: {evaluator_id}"
)


# ============================================================
# RESPONSES
# ============================================================

responses = load_evaluator_responses(
    evaluator_id
)

if responses.empty:

    answered = set()

else:

    answered = set(
        responses["image_id"]
        .astype(str)
        .tolist()
    )


n_done = len(answered)


# ============================================================
# PROGRESS
# ============================================================

st.progress(
    n_done / n_total
)

st.markdown(
    f"### Progreso: "
    f"{n_done}/{n_total} "
    f"({n_done/n_total*100:.1f}%)"
)


# ============================================================
# FINISHED
# ============================================================

if n_done >= n_total:

    st.success(
        """
        Evaluación completada.

        Muchas gracias por su participación.
        Ya puede cerrar esta ventana.
        """
    )

    st.stop()


# ============================================================
# NEXT PENDING IMAGE
# ============================================================

current_index = None

for i, image_id in enumerate(
    sample["image_id"].astype(str)
):

    if image_id not in answered:

        current_index = i
        break


if current_index is None:

    st.success(
        "Evaluación completada."
    )

    st.stop()


image_id = str(
    sample.iloc[
        current_index
    ]["image_id"]
)


# ============================================================
# IMAGE
# ============================================================

image_path = (
    IMAGES_DIR
    / f"{image_id}.png"
)


if not image_path.exists():

    st.error(
        "No fue posible cargar "
        "la captura correspondiente."
    )

    st.stop()


st.divider()

st.markdown(
    f"## Captura "
    f"{n_done + 1} de {n_total}"
)


st.image(
    str(image_path),
    use_container_width=True
)


# ============================================================
# CATEGORY
# ============================================================

st.divider()


selected = st.radio(
    "¿A qué categoría corresponde esta captura?",
    CATEGORIES,
    index=None,
    key=(
        f"category_"
        f"{evaluator_id}_"
        f"{image_id}"
    )
)


# ============================================================
# SAVE
# ============================================================

if st.button(
    "Guardar y continuar",
    type="primary",
    use_container_width=True,
    key=(
        f"save_"
        f"{evaluator_id}_"
        f"{image_id}"
    )
):

    if selected is None:

        st.warning(
            "Seleccione una categoría antes de continuar."
        )

    else:

        try:

            save_response(
                evaluator_id,
                image_id,
                selected
            )

            st.rerun()

        except Exception as exc:

            st.error(
                "No fue posible guardar la respuesta."
            )

            st.exception(exc)

