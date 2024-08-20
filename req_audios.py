import requests
import os

url = 'http://10.1.254.180:5000/transcrever '

# Arquivos de áudio para serem enviados
files = [
    ('audio', open(r'C:\\Users\Azevedo Cobretti\\OneDrive\\Documentos\\BD_audios\\6m.flac','rb')),
    ('audio', open(r'C:\\Users\Azevedo Cobretti\\OneDrive\\Documentos\\BD_audios\\6m.gsm','rb')),
    ('audio', open(r'C:\\Users\Azevedo Cobretti\\OneDrive\\Documentos\\BD_audios\\6m_mp3.mp3','rb'))
]

# Envia a requisição POST com os arquivos de áudio
response = requests.post(url, files=files)

# Exibe a resposta do servidor
print(response.json())