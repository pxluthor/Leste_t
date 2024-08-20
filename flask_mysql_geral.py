# API flask transcrição de audio com acesso ao banco de daddos Mysql.


import os
from flask import Flask, request, jsonify, render_template
import requests

from flask import send_from_directory
import pymysql
from fpdf import FPDF

from groq import Groq
import assemblyai as aai

from pydub import AudioSegment
import speech_recognition as sr


app = Flask(__name__)


app.config['UPLOAD_FOLDER'] = 'transcricoes' 
GROQ_API_KEY = "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"# colocar a chave
client = Groq(api_key=GROQ_API_KEY)


# Configuração da API AssemblyAI
ASSEMBLYAI_API_KEY = "0dd6e4398bb34fca86494411ff025f07" # colocar a chave
aai.settings.api_key = ASSEMBLYAI_API_KEY
 # Diretório onde os PDFs estão armazenados

# Configurações do banco de dados MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root123',
    'database': 'AudioDatabase'
}
app.config['UPLOAD_FOLDER'] = 'transcricoes' 


@app.route('/')
def listar_audios():
    try:
        # Conecta ao banco de dados
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Consulta todos os arquivos de áudio
        cursor.execute("""
                SELECT AudioFiles.*, transcriptions.transcription, transcriptions.transcription_path,
                AnalysisResults.analysis
                FROM AudioFiles 
                LEFT JOIN transcriptions ON AudioFiles.id = transcriptions.audio_id
                LEFT JOIN AnalysisResults ON AudioFiles.id = AnalysisResults.audio_id           
        """)

        audios = cursor.fetchall()
        cursor.close()
        connection.close()

        # Verifique se os dados estão sendo retornados corretamente
        if not audios:
            print("Nenhum áudio encontrado no banco de dados.")
        else:
            print(f"{len(audios)} arquivos de áudio encontrados.")
            for audio in audios:
                print(audio)  # Log de cada áudio para verificar

        return render_template('listar_audios.html', audios=audios)
    except Exception as e:
        print(f"Erro ao listar áudios: {str(e)}")
        return f"Erro ao listar áudios: {str(e)}"



@app.route('/download/<filename>')
def download_pdf(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)




@app.route('/transcricao/<int:audio_id>', methods=['GET'])
def obter_transcricao(audio_id):
    try:
        # Conecta ao banco de dados
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Busca a transcrição pelo audio_id
        cursor.execute("SELECT * FROM transcriptions WHERE audio_id = %s", (audio_id,))
        transcricao = cursor.fetchone()
        cursor.close()
        connection.close()

        if not transcricao:
            return jsonify({"error": "Transcrição não encontrada"}), 404

        return jsonify(transcricao)

    except Exception as e:
        return jsonify({"error": str(e)}), 500




# rota para trancrição 
@app.route('/transcrever/<int:audio_id>', methods=['GET'])
def transcrever_audio(audio_id):
    try:
        # Conecta ao banco de dados
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Busca o arquivo de áudio pelo ID
        cursor.execute("SELECT * FROM AudioFiles WHERE id = %s", (audio_id,))
        audio = cursor.fetchone()

        if not audio:
            cursor.close()
            connection.close()
            return jsonify({"error": "Arquivo de áudio não encontrado"}), 404

        # Caminho completo do arquivo de áudio
        audio_path = audio['filepath']

        # Converter o arquivo para .flac se necessário
        if audio_path.endswith('.gsm') or audio_path.endswith('.mp3'):
            audio_path = convert_to_flac(audio_path)


        try:

# divisão do audio 
            audio_segment = AudioSegment.from_file(audio_path)
            chunk_length_ms = 120000  # 2 minutos
            chunks = [audio_segment[i:i + chunk_length_ms] for i in range(0, len(audio_segment), chunk_length_ms)]


# transcrição 

            recognizer = sr.Recognizer()
            full_transcript = ""

            for i, chunk in enumerate(chunks):
                chunk_filename = save_chunk(chunk, i)
                with sr.AudioFile(chunk_filename) as source:
                    audio_data = recognizer.record(source)
                texto = recognizer.recognize_google(audio_data, language='pt-BR')
                full_transcript += texto + "\n"
                os.remove(chunk_filename)

            transcricao_texto = full_transcript
        except Exception as e:

# Se ocorrer um erro, usa o assemblyai Recognition

            try:    
                config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best, language_code="pt")
                transcriber = aai.Transcriber()

                # Transcreve o áudio
                with open(audio_path, 'rb') as audio_file:
                    transcript = transcriber.transcribe(audio_file, config=config)

                # Formata a transcrição
                transcricao_texto = transcript.text

            except Exception as google_error:
                        return jsonify({"error": f"Falha ao transcrever com ambos os serviços: {str(e)}, {str(google_error)}"}), 500
            

        # Cria e salva o arquivo de transcrição .pdf
        transcricao_dir = 'transcricoes'
        os.makedirs(transcricao_dir, exist_ok=True)
        transcricao_filename = f"transcricao_audio_{audio_id}.pdf"
        transcricao_path = os.path.join(transcricao_dir, transcricao_filename)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in transcricao_texto.split("\n"):
            pdf.multi_cell(0, 10, line)
        pdf.output(transcricao_path)

        # Insere o caminho do arquivo e a transcrição no banco de dados
        insert_query = """
        INSERT INTO Transcriptions (audio_id, transcription, transcription_path) 
        VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (audio_id, transcricao_texto, transcricao_path))
        connection.commit()

        cursor.close()
        connection.close()

        # Retorna a transcrição em formato JSON
        return jsonify({"transcription": transcricao_texto, "file_path": transcricao_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#rota para fazer a analise. 
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
        prompt = f"faça um resumo da interação identificando o motivo do contato, atendente e o cliente: "


        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}: {texto_transcricao}",
                }
            ],
            model="llama3-8b-8192",
        )

        analise = chat_completion.choices[0].message.content
        
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




# --------- FUNÇÕES AUXILIARES ------------------------------

def save_chunk(chunk, index, output_dir='chunks'):
    os.makedirs(output_dir, exist_ok=True)
    chunk_filename = os.path.join(output_dir, f"chunk_{index}.flac")
    chunk.export(chunk_filename, format="flac")
    return chunk_filename


def convert_to_flac(input_file):
    audio = AudioSegment.from_file(input_file)
    flac_filename = os.path.splitext(input_file)[0] + ".flac"
    audio.export(flac_filename, format="flac")
    return flac_filename


if __name__ == '__main__':
    app.run(debug=True)
