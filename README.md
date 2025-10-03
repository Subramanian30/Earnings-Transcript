# Transcript Assistant Setup Guide

Follow these steps to set up and run the Transcript Assistant app locally.

## 1. Download the Google Drive Folder Shared - [Link](https://drive.google.com/drive/folders/1Y8Kcyw45EwXXlR2GuRrfMcUGr2nwBqdL?usp=sharing)

Download the shared Google Drive folder containing the project files to your local machine.
Extract the folder once download is completed.

---

Here’s a polished version of your step:

---

## 2. Open Code Editor (VS Code)

1. Open the **project folder** in **Visual Studio Code**.
2. Ensure that your terminal path is inside the `transcript_assistant` directory.

   * If not, run the following command in the VS Code terminal:

   ```bash
   cd transcript_assistant
   ```
   
---

## 3. Create a Virtual Environment

Create a virtual environment to isolate dependencies:

```bash
python -m venv venv
```

---

## 4. Activate the Virtual Environment

**On macOS/Linux:**

```bash
source venv/bin/activate
```

**On Windows (Command Prompt):**

```cmd
venv\Scripts\activate
```

**On Windows (PowerShell):**

```powershell
venv\Scripts\Activate.ps1
```

---

## 5. Install Required Packages

Install the dependencies listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## 6. Set Up Environment Variables

Create a `.env` file in the `transcript_assistant` directory with the following content:

```env
AZURE_OPENAI_API_KEY= ""
AZURE_OPENAI_ENDPOINT= ""
AZURE_OPENAI_CHAT_COMPLETION_VERSION= ""
AZURE_OPENAI_EMBEDDINGS_VERSION= ""
AZURE_OPENAI_CHAT_DEPLOYMENT= ""
AZURE_OPENAI_EMBEDDING_DEPLOYMENT= ""
```

> Replace the values with your Azure OpenAI credentials.

---

## 7. Run the App

Finally, run the Streamlit app:

```bash
streamlit run app/streamlit_app.py
```

---

## Notes

* Make sure your virtual environment is activated before running the app.
* Ensure that all environment variables are correctly set in the `.env` file.
