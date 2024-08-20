from flask import Flask, request, jsonify
from groq import Groq



app = Flask(__name__)

from groq import Groq
GROQ_API_KEY = "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"# colocar a chave
client = Groq(api_key=GROQ_API_KEY)

# Dicionário mapeando ações para prompts específicos
prompts = {
    "analise da venda": "analise a seguinte transcrição de venda: ",
    "resumo da venda": "Por favor, forneça um resumo detalhado da seguinte transcrição: ",
    "avaliação de qualidade": "Por favor, avalie a qualidade desta transcrição: ",
    # Adicione outras ações e prompts conforme necessário
}

# Função para identificar a ação e gerar o prompt
def generate_prompt(action, transcription):
    if action in prompts:
        return prompts[action].format(transcription)
    else:
        return None

@app.route('/teste', methods=['POST'])
def process_transcription():
    data = request.json
    action = data.get('action')
    transcription = data.get('transcription')

    # Gerar o prompt com base na ação
    prompt = generate_prompt(action, transcription)
    
    if prompt:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt} {transcription}",
                }
            ],
            model="llama3-70b-8192",
        )

        response = chat_completion.choices[0].message.content
        # Aqui você envia o prompt para o LLM e recebe a resposta (simulação abaixo)
        
        return jsonify({"response": response})
    else:
        return jsonify({"error": "Ação desconhecida"}), 400



if __name__ == '__main__':
    app.run(debug=True)
