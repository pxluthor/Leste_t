from flask import Flask, request, jsonify
import logging
import os
from groq import Groq
import google.generativeai as genai
import Prompts

# Configuração do logger para registrar erros e informações
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializa o Flask
app = Flask(__name__)

# Carrega os prompts
prompts = Prompts.prompts

# Configura e inicializa os modelos LLM
client = Groq(api_key="") 
genai.configure(api_key="")

# Função que executa o modelo Groq
def run_groq(prompt, text):
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": f"{text}: {prompt}"}],
            model="llama3-70b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in Groq processing: {e}")
        return None

# Função que executa o fallback com Gemini
def run_gemini(prompt, text):
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        response = model.generate_content(f"{text}: {prompt}")
        return response.text
    except Exception as e:
        logger.error(f"Error in Gemini processing: {e}")
        return "An error occurred while processing the request with the fallback LLM."

# Função que valida a entrada
def validate_input(keyword, text):
    if not keyword or keyword not in prompts:
        logger.error("Invalid keyword provided.")
        return False, "Invalid keyword. Please provide a valid keyword."
    if not text or len(text.strip()) == 0:
        logger.error("Empty or invalid text provided.")
        return False, "Text cannot be empty. Please provide valid text."
    return True, ""

# Função que executa o LLM com fallback
def run_with_fallback(prompt, text):
    result = run_groq(prompt, text)
    if not result or len(result.strip()) == 0:
        logger.warning("Erro ao utilizar a Groq, utilizando o Gemini.")
        result = run_gemini(prompt, text)
    return result

# Rota que processa a requisição
@app.route('/process', methods=['POST'])
def process_request():
    data = request.json
    keyword = data.get("keyword")
    text = data.get("text")
    
    # Validação da entrada
    is_valid, error_message = validate_input(keyword, text)
    if not is_valid:
        return jsonify({"error": error_message}), 400
    
    # Processamento baseado na palavra-chave
    if keyword in prompts:
        prompt = prompts[keyword]
        result = run_with_fallback(prompt, text)
    else:
        logger.info("Keyword not recognized, using default handling.")
        result = run_gemini(f"Process the following text: {text}", text)
    
    return jsonify({"result": result})

# Inicializa o servidor Flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
