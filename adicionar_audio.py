import os
import pymysql
from pydub.utils import mediainfo
from pydub import AudioSegment

# Conecte-se ao banco de dados MySQL
connection = pymysql.connect(
    host='localhost',
    user='root',
    password='root123 ',
    database='AudioDatabase'
)

cursor = connection.cursor()

# Caminho para a pasta de áudio
audio_folder = r'C:\\Users\\Azevedo Cobretti\\OneDrive\\Documentos\\BD_audios'

# Iterando sobre os arquivos de áudio na pasta
for filename in os.listdir(audio_folder):
    if filename.endswith(('.mp3', '.flac', '.gsm')):  
        filepath = os.path.join(audio_folder, filename)
        audio_info = mediainfo(filepath)
        duration = float(audio_info['duration'])

        # Insira os dados no banco de dados
        sql = "INSERT INTO AudioFiles (filename, filepath, format, duration) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (filename, filepath, audio_info['format_name'], duration))

# Confirme as mudanças
connection.commit()

# Feche a conexão
cursor.close()
connection.close()
