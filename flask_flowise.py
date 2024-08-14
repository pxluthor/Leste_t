from flask import Flask, request, jsonify, render_template
import pymysql
from fpdf import FPDF
import os
from flask import send_from_directory
from pydub import AudioSegment
import speech_recognition as sr
from groq import Groq
import requests



app = Flask(__name__)


GROQ_API_KEY = ""
client = Groq(api_key=GROQ_API_KEY)


# Configurações do banco de dados MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root123',
    'database': 'AudioDatabase'
}

app.config['UPLOAD_FOLDER'] = 'transcricoes'  # Diretório onde os PDFs estão armazenados

def convert_to_flac(input_file):
    audio = AudioSegment.from_file(input_file)
    flac_filename = os.path.splitext(input_file)[0] + ".flac"
    audio.export(flac_filename, format="flac")
    return flac_filename

def save_chunk(chunk, index, output_dir='chunks'):
    os.makedirs(output_dir, exist_ok=True)
    chunk_filename = os.path.join(output_dir, f"chunk_{index}.flac")
    chunk.export(chunk_filename, format="flac")
    return chunk_filename



@app.route('/')
def listar_audios():
    try:
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT AudioFiles.*, Transcriptions.transcription, Transcriptions.transcription_path,
            AnalysisResults.analysis
            FROM AudioFiles 
            LEFT JOIN Transcriptions ON AudioFiles.id = Transcriptions.audio_id
            LEFT JOIN AnalysisResults ON AudioFiles.id = AnalysisResults.audio_id           
        """)
        audios = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('listar_audios.html', audios=audios)
    except Exception as e:
        return f"Erro ao listar áudios: {str(e)}"



@app.route('/download/<filename>')
def download_pdf(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)



@app.route('/transcricao/<int:audio_id>', methods=['GET'])
def obter_transcricao(audio_id):
    try:
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM Transcriptions WHERE audio_id = %s", (audio_id,))
        transcricao = cursor.fetchone()
        cursor.close()
        connection.close()
        if not transcricao:
            return jsonify({"error": "Transcrição não encontrada"}), 404
        return jsonify(transcricao)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/transcrever/<int:audio_id>', methods=['GET'])
def transcrever_audio(audio_id):
    try:
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM AudioFiles WHERE id = %s", (audio_id,))
        audio = cursor.fetchone()

        if not audio:
            cursor.close()
            connection.close()
            return jsonify({"error": "Arquivo de áudio não encontrado"}), 404

        audio_path = audio['filepath']

        # Converter o arquivo para .flac se necessário
        if audio_path.endswith('.gsm') or audio_path.endswith('.mp3'):
            audio_path = convert_to_flac(audio_path)

        audio_segment = AudioSegment.from_file(audio_path)
        chunk_length_ms = 120000  # 2 minutos
        chunks = [audio_segment[i:i + chunk_length_ms] for i in range(0, len(audio_segment), chunk_length_ms)]

        recognizer = sr.Recognizer()
        full_transcript = ""

        for i, chunk in enumerate(chunks):
            chunk_filename = save_chunk(chunk, i)
            with sr.AudioFile(chunk_filename) as source:
                audio_data = recognizer.record(source)
            texto = recognizer.recognize_google(audio_data, language='pt-BR')
            full_transcript += texto + "\n"
            os.remove(chunk_filename)

        transcricao_dir = 'transcricoes'
        os.makedirs(transcricao_dir, exist_ok=True)
        transcricao_filename = f"trancricao_id_{audio_id}.pdf"
        transcricao_path = os.path.join(transcricao_dir, transcricao_filename)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in full_transcript.split("\n"):
            pdf.multi_cell(0, 10, line)
        pdf.output(transcricao_path)

        insert_query = """
        INSERT INTO Transcriptions (audio_id, transcription, transcription_path) 
        VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (audio_id, full_transcript, transcricao_path))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"transcription": full_transcript, "file_path": transcricao_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/analisar/<int:audio_id>', methods=['GET'])
def analisar_transcricao(audio_id):
    try:
        # Conecta ao banco de dados
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Busca a transcrição pelo audio_id
        cursor.execute("SELECT transcription FROM Transcriptions WHERE audio_id = %s", (audio_id,))
        transcricao = cursor.fetchone()

        if not transcricao:
            cursor.close()
            connection.close()
            return jsonify({"error": "Transcrição não encontrada"}), 404

        texto_transcricao = transcricao['transcription']
        question = f"faça um resumo da interação identificando o motivo do contato, atendente e o cliente: {texto_transcricao}"

        # Requisição à API externa a API do flowise
        api_url = "https://pxluthor-flowiseia.hf.space/api/v1/prediction/4abdc2d5-f2f0-4f27-a307-b0f4087de29f" # alterar para a rota do flowise
        headers = {"Content-Type": "application/json"}
        payload = {
            "question": question,
            "context": texto_transcricao
        }

        response = requests.post(api_url, json=payload, headers=headers)

        if response.status_code != 200:
            return jsonify({"error": "Erro na requisição à API externa", "details": response.text}), response.status_code

        analise = response.json().get('text')  # pega o retorno da API 

        # Insere o resultado da análise no banco de dados
        insert_query = """
        INSERT INTO AnalysisResults (audio_id, analysis) 
        VALUES (%s, %s)
        """
        cursor.execute(insert_query, (audio_id, analise))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"analysis": analise})

    except Exception as e:
        return jsonify({"error": str(e)}), 500    

if __name__ == '__main__':
    app.run(debug=True)
