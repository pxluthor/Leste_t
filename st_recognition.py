import os
import streamlit as st
from pydub import AudioSegment
from groq import Groq
import google.generativeai as genai
from docx import Document
from fpdf import FPDF
import assemblyai as aai
from pydub.utils import which
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Configuração das chaves de API
api_key_groq = st.secrets["api_keys"]["api_key4"]
api_key_gemini = st.secrets["api_keys"]["api_key1"]
aai.settings.api_key = ""
client = Groq(api_key=api_key_groq)

# Configuração da API Gemini
genai.configure(api_key=api_key_gemini)
generation_config = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}
safety_settings = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

model_g = genai.GenerativeModel(model_name='models/gemini-1.5-flash-latest', generation_config=generation_config, safety_settings=safety_settings)

config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best, language_code="pt")

def convert_to_flac(audio_path):
    audio = AudioSegment.from_file(audio_path)
    flac_path = os.path.splitext(audio_path)[0] + ".flac"
    audio.export(flac_path, format="flac")
    return flac_path

def save_chunk(chunk, index):
    chunk_filename = f"chunk_{index}.flac"
    chunk.export(chunk_filename, format="flac")
    return chunk_filename

def transcribe_audio(filepath):
    # Converter o arquivo para .flac se necessário
    if filepath.endswith('.gsm') or filepath.endswith('.mp3'):
        filepath = convert_to_flac(filepath)

    audio_segment = AudioSegment.from_file(filepath)
    chunk_length_ms = 120000  # 2 minutos
    chunks = [audio_segment[i:i + chunk_length_ms] for i in range(0, len(audio_segment), chunk_length_ms)]

    full_transcript = ""
    transcriber = aai.Transcriber()

    for i, chunk in enumerate(chunks):
        chunk_filename = save_chunk(chunk, i)
        transcript = transcriber.transcribe(chunk_filename, config=config)

        if transcript.status == aai.TranscriptStatus.error:
            full_transcript += f"[Erro ao transcrever o chunk {i}: {transcript.error}]\n"
        else:
            full_transcript += transcript.text + "\n"

        os.remove(chunk_filename)

    return full_transcript

def export_to_pdf(transcription):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in transcription:
        line_str = line.encode('latin1', 'ignore').decode('latin1')
        pdf.multi_cell(0, 10, line_str)
    pdf_file = "transcription.pdf"
    pdf.output(pdf_file)
    return pdf_file

def export_to_docx(transcription):
    doc = Document()
    for line in transcription:
        doc.add_paragraph(line)
    doc_file = "transcription.docx"
    doc.save(doc_file)
    return doc_file

def role_to_streamlit(role):
    return "assistente" if role == "model" else role

def main():
    st.title("💬 Chat - Transcription audio 🎙🔉")

    if "chat" not in st.session_state:
        st.session_state.chat = []
        st.session_state.history = []

    if "transcricao_feita" not in st.session_state:
        st.session_state.transcricao_feita = False
       
    if "transcricao" not in st.session_state:
        st.session_state.transcricao = ""

    if "pdf_downloads" not in st.session_state:
        st.session_state.pdf_downloads = 0
    if "docx_downloads" not in st.session_state:
        st.session_state.docx_downloads = 0

    with st.sidebar:
        st.button("NOVO CHAT", on_click=limpar_chat)

        if st.session_state.transcricao_feita:
            with open("transcription.pdf", "rb") as f:
                st.download_button(
                    label=f"Download PDF ({st.session_state.pdf_downloads})",
                    data=f,
                    file_name="transcription.pdf",
                    mime="application/pdf"
                )

            with open("transcription.docx", "rb") as f:
                st.download_button(
                    label=f"Download DOCX ({st.session_state.docx_downloads})",
                    data=f,
                    file_name="transcription.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

    for message in st.session_state.chat:
        role = "user" if message["role"] == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(message['text'])

    if prompt := st.chat_input("Como posso ajudar?"):
        st.session_state.chat.append({"role": "user", "text": prompt})
        st.session_state.history.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        response = client.chat.completions.create(
            messages=st.session_state.history,
            model="llama3-70b-8192"
        )
        response_text = response.choices[0].message.content

        st.session_state.chat.append({"role": "assistant", "text": response_text})
        st.session_state.history.append({"role": "assistant", "content": response_text})

        with st.chat_message("assistant"):
            st.markdown(response_text)

    arquivo_carregado = st.sidebar.file_uploader("Carregar arquivo de áudio (GSM ou MP3)")

    if arquivo_carregado:
        st.sidebar.markdown("# PLAY AUDIO 🔉 ")

        @st.cache_data
        def carregar_audio(arquivo_carregado):
            return arquivo_carregado.read()

        audio_data = carregar_audio(arquivo_carregado)

        if arquivo_carregado.name.endswith(".gsm"):
            temp_filename = "audio_temp.flac"
            with open(temp_filename, "wb") as f:
                f.write(audio_data)
            AudioSegment.from_file(temp_filename, format="gsm").export(temp_filename, format="flac")
            audio_data = open(temp_filename, "rb").read()
        else:
            temp_filename = "audio_temp.flac"    
            with open(temp_filename, "wb") as f:
                f.write(audio_data)

        st.sidebar.audio(audio_data, format="audio/mpeg", loop=False)
        st.sidebar.info("Audio carregado!")

        if not st.session_state.transcricao_feita and st.sidebar.button("Fazer transcrição"):
            st.write("Realizando o tratamento do áudio...")
            st.session_state.file_path = temp_filename
            transcription = transcribe_audio(st.session_state.file_path)
            st.session_state.chat.append({"role": "system", "text": f"Transcrição: \n {transcription}"})
            st.session_state.history.append({"role": "system", "content": f"Transcrição: \n {transcription}"})

            with st.expander("Mostrar lista"):
                st.write(f"Transcrição: \n {transcription}")

            st.write("Processando transcrição ...")

            prompt3 = f'''realize a transcrição completa de conversa que vem na lista: {transcription} identificando a fala de cada interlocutor e o tempo correto de cada fala. 
            siga o modelo de transcrição para a resposta.

            Modelo para transcrição:
            tempo de fala (tempo real do arquivo)

            interlocutor1: (fala)(\n).
            interlocutor2: (fala)(\n).

            contexto:
            conversa de ligação cliente entra em contato com o call center da Leste telecom, empresa de internet 
            O atendente sempre inicia a interação com o cliente fazendo a saudação e 
            perguntando como pode ajudar.

            Utilize quebra de linha para melhorar a apresentação no PDF. 
            Ajuste a transcrição para melhor visualização da interação na tela.

            Sempre responda em português do Brasil e retorne a transcrição completa.
            '''
            prompt4 = f''' {transcription} retorne motivo do contato e um resumo do que foi feito. 

            '''
            try:
                resp = model_g.generate_content(prompt4)
                response_final = resp.text

            except ValueError as e:
                st.error("Erro ao processar a resposta do modelo Gemini. Usando o modelo Groq para a transcrição.")
                response_final = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt4}],
                    model="llama3-70b-8192"
                ).choices[0].message.content

                with st.chat_message("assistente"):
                    st.write("Resposta Groq")
                    st.markdown(response_final)
                    st.session_state.chat.append({"role": "assistente", "text": response_final})
                    st.session_state.history.append({"role": "assistant", "content": response_final})

            else:
                with st.chat_message("assistente"):
                    st.write("Resposta Gemini")
                    st.markdown(response_final)
                    st.session_state.chat.append({"role": "assistente", "text": response_final})
                    st.session_state.history.append({"role": "assistant", "content": response_final})
            
            pdf_file = export_to_pdf(transcription.splitlines())
            docx_file = export_to_docx(transcription.splitlines())

            with open(pdf_file, "rb") as f:
                st.download_button(
                    label="Download PDF",
                    data=f,
                    file_name=pdf_file,
                    mime="application/pdf"
                )

            with open(docx_file, "rb") as f:
                st.download_button(
                    label="Download DOCX",
                    data=f,
                    file_name=docx_file,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            st.session_state.transcricao = transcription
            st.session_state.transcricao_feita = True

            

            export_to_pdf(transcription)
            export_to_docx(transcription)

def limpar_chat():
    st.session_state.chat = []
    st.session_state.history = []
    st.session_state.transcricao_feita = False

if __name__ == "__main__":
    main()
