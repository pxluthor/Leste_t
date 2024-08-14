# API flask transcrição de audio 


from flask import Flask, request, jsonify, render_template
from flask import send_from_directory
import pymysql
from fpdf import FPDF
import os
from groq import Groq
import assemblyai as aai
import requests
from pydub import AudioSegment

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'transcricoes' 
GROQ_API_KEY = ""# colocar a chave
client = Groq(api_key=GROQ_API_KEY)


# Configuração da API AssemblyAI
ASSEMBLYAI_API_KEY = "" # colocar a chave
aai.settings.api_key = ASSEMBLYAI_API_KEY

# Configurações do banco de dados MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root123',
    'database': 'AudioDatabase'
}

def convert_to_flac(input_file):
    audio = AudioSegment.from_file(input_file)
    flac_filename = os.path.splitext(input_file)[0] + ".flac"
    audio.export(flac_filename, format="flac")
    return flac_filename

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


   

    
app.config['UPLOAD_FOLDER'] = 'transcricoes'  # Diretório onde os PDFs estão armazenados

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

        # Configura a transcrição
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best, language_code="pt")
        transcriber = aai.Transcriber()

        # Transcreve o áudio
        with open(audio_path, 'rb') as audio_file:
            transcript = transcriber.transcribe(audio_file, config=config)

        # Formata a transcrição
        transcricao_texto = transcript.text

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

        # Requisição à API externa a API do flowise
       # api_url = "https://pxluthor-flowiseia.hf.space/api/v1/prediction/4abdc2d5-f2f0-4f27-a307-b0f4087de29f" # alterar para a rota do flowise
       # headers = {"Content-Type": "application/json"}
       # payload = {"question": f"{texto_transcricao}, {prompt}"}

       # response = requests.post(api_url, json=payload, headers=headers)


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




        #if response.status_code != 200:
         #   return jsonify({"error": "Erro na requisição à API externa", "details": response.text}), response.status_code

        #analise = response.json().get('text')  # pega o retorno da API 

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




#if __name__ == '__main__':
 #   app.run(debug=True)
