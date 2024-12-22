from app import db
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

def run_migration():
    # Connexion à MySQL
    connection = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )
    cursor = connection.cursor()

    try:
        # Lecture du fichier SQL
        with open('migrations/add_task_fields.sql', 'r') as file:
            sql_commands = file.read()

        # Exécution des commandes SQL
        for command in sql_commands.split(';'):
            if command.strip():
                cursor.execute(command)

        # Validation des changements
        connection.commit()
        print("Migration réussie !")

    except Exception as e:
        print(f"Erreur lors de la migration : {str(e)}")
        connection.rollback()

    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    run_migration()
