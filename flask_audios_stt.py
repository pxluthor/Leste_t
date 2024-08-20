# atualizado 19082024.
# rota /transcribe: trancscreve audio, ou uma lista de audios.  
# rota /analyze: código ajustado para receber mais de um audio em um array no payload e processa-los separadamente,porém retornando a response na mesma requisição
# reta /context: código ajustado para receber mais de um audio em uma lista no payload e processa-los juntos como contexto, retornando a analise na mesma response.
# necessário ter no mesmo diretório as pastas [uploads], [trancricoes] e [chunks]
# rodar: flask --app hello run –host 0.0.0.0 --debug


from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import speech_recognition as sr
from pydub import AudioSegment
from fpdf import FPDF
from groq import Groq
import time
import assemblyai as aai


app = Flask(__name__)

GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

ASSEMBLYAI_API_KEY = "0dd6e4398bb34fca86494411ff025f07" # colocar a chave
aai.settings.api_key = ASSEMBLYAI_API_KEY

# Configurações de upload de arquivo 
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'gsm', 'mp3', 'flac'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS





@app.route('/transcribe', methods=['POST'])
def transcrever_audio():
    try:
        # Verifica se algum arquivo foi enviado
        if 'audio' not in request.files:
            return jsonify({"error": "Nenhum arquivo de áudio encontrado"}), 400

        files = request.files.getlist('audio')
        transcricoes = []

        for file in files:
            # Verifica se o arquivo é válido
            if file.filename == '':
                return jsonify({"error": "Nenhum arquivo selecionado"}), 400

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Converter o arquivo para .flac se necessário
                if filepath.endswith('.gsm') or filepath.endswith('.mp3'):
                    filepath = convert_to_flac(filepath)

                audio_segment = AudioSegment.from_file(filepath)
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

                # Cria o PDF com a transcrição
                transcricao_dir = 'transcricoes'
                os.makedirs(transcricao_dir, exist_ok=True)
                transcricao_filename = f"transcricao_{filename}.pdf"
                transcricao_path = os.path.join(transcricao_dir, transcricao_filename)

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                for line in full_transcript.split("\n"):
                    pdf.multi_cell(0, 10, line)
                pdf.output(transcricao_path)

                # Adiciona a transcrição atual à lista de transcrições
                transcricoes.append({"filename": filename, "transcription": full_transcript, "file_path": transcricao_path})

            else:
                return jsonify({"error": f"Tipo de arquivo inválido para o arquivo {file.filename}"}), 400

        # Retorna todas as transcrições na mesma requisição
        return jsonify(transcricoes)

    except Exception as e:
        return jsonify({"error": str(e)}), 500






#rota faz a analise de cada array de trancrição 
@app.route('/analyze', methods=['POST'])
def analisar_transcricao():
    try:
        # Obtém as transcrições do corpo da requisição
        transcricoes = request.json.get('transcricoes', [])

        if not transcricoes:
            return jsonify({"error": "Nenhuma transcrição fornecida"}), 400

        # Itera sobre as transcrições e realiza a análise
        analisadas = []
        for transcricao in transcricoes:
            prompt = f"faça um resumo da interação: {transcricao}"

            chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}",
                }
            ],
            model="llama3-70b-8192",
        )
            analise = chat_completion.choices[0].message.content

            analisadas.append({'transcricao': transcricao, 'analise': analise})

        return jsonify({"analisadas": analisadas})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/context', methods=['POST'])
def analisar_transcricao2():
    try:
        # Obtém as transcrições do corpo da requisição
        transcricoes = request.json.get('transcricoes', [])

        if not transcricoes:
            return jsonify({"error": "Nenhuma transcrição fornecida"}), 400

        # Junta todas as transcrições em um único texto
        texto_completo = "\n".join(transcricoes)

        # Cria o prompt com todas as transcrições
        prompt = f"faça um resumo da interação: {texto_completo}"

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}",
                }
            ],
            model="llama3-70b-8192",
        )
            
        analise = chat_completion.choices[0].message.content
        
        


        # Retorna a análise
        return jsonify({"analise": analise})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/transcrever', methods=['POST'])
def transcrever_audio2():
    try:
        start_time = time.time()
        # Verifica se algum arquivo foi enviado
        if 'audio' not in request.files:
            return jsonify({"error": "Nenhum arquivo de áudio encontrado"}), 400

        files = request.files.getlist('audio')
        transcricoes = []

        for file in files:
            # Verifica se o arquivo é válido
            if file.filename == '':
                return jsonify({"error": "Nenhum arquivo selecionado"}), 400

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Converter o arquivo para .flac se necessário
                if filepath.endswith('.gsm') or filepath.endswith('.mp3'):
                    filepath = convert_to_flac(filepath)

                # Primeiro tenta usar AssemblyAI para a transcrição
                try:
                    config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best, language_code="pt")
                    transcriber = aai.Transcriber()

                    with open(filepath, 'rb') as audio_file:
                        transcript = transcriber.transcribe(audio_file, config=config)    

                    transcricao_texto = transcript.text
                except Exception as e:
                    # Se ocorrer um erro, usa o Google Speech Recognition
                    try:
                        audio_segment = AudioSegment.from_file(filepath)
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

                        transcricao_texto = full_transcript
                    except Exception as google_error:
                        return jsonify({"error": f"Falha ao transcrever com ambos os serviços: {str(e)}, {str(google_error)}"}), 500

                # Cria o PDF com a transcrição
                transcricao_dir = 'transcricoes'
                os.makedirs(transcricao_dir, exist_ok=True)
                transcricao_filename = f"transcricao_{filename}.pdf"
                transcricao_path = os.path.join(transcricao_dir, transcricao_filename)

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                for line in transcricao_texto.split("\n"):
                    pdf.multi_cell(0, 10, line)
                pdf.output(transcricao_path)

                end_time = time.time()
                time_exec = end_time - start_time

                # Adiciona a transcrição atual à lista de transcrições
                transcricoes.append({"filename": filename, "transcription": transcricao_texto, "file_path": transcricao_path, "time": f"{time_exec:.4f}"})
            else:
                return jsonify({"error": f"Tipo de arquivo inválido para o arquivo {file.filename}"}), 400

        # Retorna todas as transcrições na mesma requisição
        return jsonify(transcricoes)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Funções auxiliares 
#--------------------------------------------------------------------------------#


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

if __name__ == '__main__':
    app.run(debug=True)


