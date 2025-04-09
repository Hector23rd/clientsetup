import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL
import dash_bootstrap_components as dbc
import requests
import pandas as pd

# --------------------------
# CONFIG / CONSTANTS
# --------------------------
API_KEY = "fVprYoK5HcrENL3m34kDa8JZIQMg1ed2XmF0x"
SHEET_ID = "FmhVrx5GcVHffF8jq25qQgcqfm6Jm995fPJGVxr1"
SMARTSHEET_BASE_URL = "https://api.smartsheet.com/2.0/sheets"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

COLOR_SCHEME = {
    "primary": "#e53130",
    "secondary": "#c62828",
    "accent": "#ff5252",
    "background": "#f8f9fa",
    "text": "#2b2d42"
}

DEFAULT_INPUT_STYLE = {
    "width": "auto",
    "whiteSpace": "nowrap",
    "display": "inline-block",
    "minWidth": "50px",
    "maxWidth": "300px",
    "padding": "2px"
}

# --------------------------
# HELPER FUNCTIONS
# --------------------------
def is_image_url(url: str) -> bool:
    """Check whether a URL points to an image based on common extensions."""
    img_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    return any(url.lower().endswith(ext) for ext in img_extensions)

def render_attachment(raw_value, row_id, edit_mode):
    """Render attached files with a thumbnail preview if an image is detected."""
    elements = []
    # Handle multiple attachments if provided as a list.
    if isinstance(raw_value, list):
        for file in raw_value:
            if isinstance(file, dict):
                file_url = file.get("url", "#")
                file_name = file.get("name", "File")
            else:
                file_url = file
                file_name = "Open Attachment"
            if is_image_url(file_url):
                elements.append(html.Img(src=file_url,
                                         style={"width": "150px", "height": "auto", "margin": "5px"}))
            elements.append(html.Div(html.A(file_name, href=file_url, target="_blank")))
        # Delete button for attachment (if needed later)
        elements.append(
            dbc.Button("Delete File",
                       id={"type": "delete-file", "row_id": row_id, "col": "Attachment"},
                       color="danger", size="sm", className="ml-2")
        )
        return html.Div(elements)
    else:
        if is_image_url(raw_value):
            elements.append(html.Img(src=raw_value,
                                     style={"width": "150px", "height": "auto", "cursor": "pointer"}))
        elements.append(html.A("Open Attachment", href=raw_value, target="_blank", style={"marginLeft": "10px"}))
        elements.append(
            dbc.Button("Delete File",
                       id={"type": "delete-file", "row_id": row_id, "col": "Attachment"},
                       color="danger", size="sm", className="ml-2")
        )
        return html.Div(elements)

# --------------------------
# DATA UTILITIES
# --------------------------
def fetch_smartsheet_data(sheet_id: str) -> dict:
    """Fetch fresh data from Smartsheet."""
    url = f"{SMARTSHEET_BASE_URL}/{sheet_id}"
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return {}

def rows_to_dataframe(sheet_json: dict) -> pd.DataFrame:
    """
    Convert Smartsheet JSON into a DataFrame.
    Adds a hidden _row_id field for tracking.
    """
    if not sheet_json or "columns" not in sheet_json or "rows" not in sheet_json:
        return pd.DataFrame()
    col_map = {col["id"]: col["title"] for col in sheet_json["columns"]}
    data_rows = []
    for row in sheet_json["rows"]:
        row_data = {"_row_id": row.get("id")}
        for cell in row.get("cells", []):
            col_id = cell.get("columnId")
            col_title = col_map.get(col_id, f"Unknown_{col_id}")
            row_data[col_title] = cell.get("value", "")
        data_rows.append(row_data)
    return pd.DataFrame(data_rows).convert_dtypes()

def delete_smartsheet_row(sheet_id: str, row_id) -> dict:
    """Delete a row on Smartsheet."""
    url = f"{SMARTSHEET_BASE_URL}/{sheet_id}/rows?ids={row_id}"
    try:
        resp = requests.delete(url, headers=HEADERS)
        resp.raise_for_status()
        print(f"Delete response for row {row_id}:", resp.json())
        return resp.json()
    except requests.RequestException as e:
        print(f"Error deleting row {row_id}: {e}")
        return {}

# --------------------------
# DASH APP SETUP
# --------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app.layout = dbc.Container([
    # Top Row: Client Dropdown
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Label("Select Client", className="small fw-bold mb-2"),
                    dcc.Dropdown(
                        id="client-dropdown",
                        placeholder="Search clients...",
                        searchable=True,
                        clearable=True,
                        style={"width": "100%"}
                    )
                ])
            ], className="shadow-sm border-0")
        ], xs=12, sm=12, md=6, lg=4, style={"padding": "10px"})
    ], className="mb-3"),

    # Top Row: Edit and Save Buttons
    dbc.Row([
        dbc.Col([
            dbc.Button("Edit", id="toggle-edit", color="secondary", size="lg",
                       className="me-2", style={"width": "150px"})
        ], width="auto"),
        dbc.Col([
            dbc.Button("Save", id="save-button", color="success", size="lg",
                       disabled=True, style={"width": "150px"})
        ], width="auto")
    ], justify="center", className="mb-3"),

    # Main Container: Submission Cards (with header)
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Loading(
                        html.Div(id="submission-cards-container"),
                        color=COLOR_SCHEME["primary"]
                    )
                ])
            ], className="shadow-sm border-0 mb-3")
        ], width=12)
    ]),

    # Output Message Area (for save actions)
    dbc.Row([
        dbc.Col([
            html.Div(id="save-output", className="mt-2")
        ])
    ]),

    # Hidden Stores
    dcc.Store(id="stored-data", data={}),
    dcc.Store(id="edit-mode-store", data=False)
], fluid=True, style={
    "backgroundColor": COLOR_SCHEME["background"],
    "minHeight": "100vh",
    "paddingLeft": "20px",
    "paddingRight": "20px"
})

# --------------------------
# CALLBACKS
# --------------------------
@app.callback(
    Output("client-dropdown", "options"),
    Input("client-dropdown", "search_value")
)
def update_client_dropdown(search_value):
    """Fetch and return client names from Smartsheet (requires a 'Client' column)."""
    sheet_json = fetch_smartsheet_data(SHEET_ID)
    df = rows_to_dataframe(sheet_json)
    if "Client" in df.columns:
        clients = sorted(df["Client"].dropna().unique())
    else:
        clients = []
    return [{"label": c, "value": c} for c in clients]

@app.callback(
    Output("edit-mode-store", "data"),
    Output("toggle-edit", "children"),
    Output("save-button", "disabled"),
    Input("toggle-edit", "n_clicks"),
    State("edit-mode-store", "data")
)
def toggle_edit_mode(n_clicks, current_mode):
    """Toggle edit mode state; return updated state, button label, and save button enable flag."""
    if n_clicks:
        current_mode = not current_mode
    button_label = "Disable Edit" if current_mode else "Edit"
    save_disabled = not current_mode
    return current_mode, button_label, save_disabled

@app.callback(
    Output("submission-cards-container", "children"),
    Output("stored-data", "data"),
    Input("client-dropdown", "value"),
    Input({"type": "delete-submission", "row_id": ALL}, "n_clicks"),
    Input("edit-mode-store", "data")
)
def update_submission_cards(selected_client, delete_clicks, edit_mode):
    ctx = callback_context
    if not selected_client:
        return dbc.Alert("Please select a client to view details.", color="info"), {}

    # Handle deletion trigger from within a submission card.
    if ctx.triggered and ctx.triggered[0]["prop_id"].startswith("{"):
        try:
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
            comp_id = eval(triggered_id)
            row_id = comp_id["row_id"]
            delete_smartsheet_row(SHEET_ID, row_id)
        except Exception as e:
            print("Error during deletion:", e)

    sheet_json = fetch_smartsheet_data(SHEET_ID)
    df = rows_to_dataframe(sheet_json)
    if df.empty or "Client" not in df.columns:
        return dbc.Alert("No data found.", color="warning"), {}
    filtered = df[df["Client"] == selected_client]
    if filtered.empty:
        return dbc.Alert(f"No details found for '{selected_client}'.", color="warning"), {}

    submission_cards = []
    stored = {}
    ordered_cols = [col["title"] for col in sheet_json.get("columns", []) if col.get("title")]

    # Create header showing the selected client.
    header = html.H5(f"Submission Details for {selected_client}", className="mb-4")

    for _, row_data in filtered.iterrows():
        row_id = row_data.get("_row_id")
        stored[str(row_id)] = row_data.to_dict()
        field_components = []
        for col in ordered_cols:
            if col not in row_data:
                continue
            raw_value = row_data[col]
            if pd.isna(raw_value) or raw_value == "":
                continue

            if col.strip().lower() == "map":
                content = html.Div([
                    html.A(
                        html.Img(src=raw_value,
                                 style={"width": "150px", "height": "auto", "cursor": "pointer"}),
                        href=raw_value, target="_blank"
                    ),
                    dbc.Input(
                        id={"type": "editable-field", "row_id": row_id, "col": col},
                        value=raw_value, type="text",
                        style=DEFAULT_INPUT_STYLE,
                        disabled=not edit_mode,
                        className="mt-1"
                    )
                ])
            elif col.strip().lower() == "attachment":
                content = render_attachment(raw_value, row_id, edit_mode)
            elif col.strip().lower() == "status":
                content = dbc.Select(
                    id={"type": "editable-field", "row_id": row_id, "col": col},
                    options=[
                        {"label": "Pending", "value": "Pending"},
                        {"label": "Completed", "value": "Completed"}
                    ],
                    value=raw_value,
                    style=DEFAULT_INPUT_STYLE,
                    disabled=not edit_mode
                )
            else:
                content = dbc.Input(
                    id={"type": "editable-field", "row_id": row_id, "col": col},
                    value=raw_value, type="text",
                    style=DEFAULT_INPUT_STYLE,
                    disabled=not edit_mode
                )
            field_components.append(
                html.Div([
                    dbc.Label(col, className="small fw-bold"),
                    content
                ], className="mb-2")
            )
        # Single delete button per submission.
        delete_button = dbc.Button("Delete Submission",
                                   id={"type": "delete-submission", "row_id": row_id},
                                   color="danger", className="mb-2")
        submission_card = dbc.Card(
            dbc.CardBody(field_components + [delete_button]),
            className="mb-3", outline=True
        )
        submission_cards.append(submission_card)
    return [header] + submission_cards, stored

# --------------------------
# SAVE CHANGES CALLBACK (BATCHED)
# --------------------------
@app.callback(
    Output("save-output", "children"),
    Input("save-button", "n_clicks"),
    State({"type": "editable-field", "row_id": ALL, "col": ALL}, "value"),
    State({"type": "editable-field", "row_id": ALL, "col": ALL}, "id"),
    State("stored-data", "data"),
    prevent_initial_call=True
)
def save_changes(n_clicks, values, ids, stored_data):
    if not n_clicks:
        return ""
    # Fetch current sheet metadata.
    sheet_json = fetch_smartsheet_data(SHEET_ID)
    if not sheet_json or "columns" not in sheet_json:
        return "No Smartsheet data available for saving."

    # Build reverse mapping: column title -> column id.
    reverse_column_map = {col["title"]: col["id"] for col in sheet_json["columns"]}

    # Group new values by row.
    updates_by_row = {}
    for val, comp_id in zip(values, ids):
        row_id = str(comp_id["row_id"])
        col = comp_id["col"]
        # Skip attachment fields (view-only).
        if col.strip().lower() == "attachment":
            continue
        if row_id not in updates_by_row:
            updates_by_row[row_id] = {}
        updates_by_row[row_id][col] = val

    update_rows = []
    for row_id, updated_fields in updates_by_row.items():
        original = stored_data.get(row_id, {})
        updates = []
        for col, new_val in updated_fields.items():
            orig_val = original.get(col, "")
            if str(orig_val) != str(new_val):
                col_id = reverse_column_map.get(col)
                if col_id:
                    cell_data = {"columnId": col_id, "value": new_val, "strict": False}
                    updates.append(cell_data)
        if updates:
            try:
                update_rows.append({"id": int(row_id), "cells": updates})
            except Exception as e:
                print(f"Error converting row id {row_id} to int: {e}")

    if update_rows:
        url_update = f"{SMARTSHEET_BASE_URL}/{SHEET_ID}/rows"
        # Pass the updates as a JSON array (not wrapped in a key) per the working sample.
        response = requests.put(url_update, headers=HEADERS, json=update_rows)
        if response.status_code not in (200, 204):
            print(f"Failed to update rows: {response.text}")
            return "Failed to update some rows."
        return "Changes saved successfully to Smartsheet!"
    return "No changes detected."

# --------------------------
# MAIN
# --------------------------
if __name__ == "__main__":
    app.run_server(debug=True, port=8051)
