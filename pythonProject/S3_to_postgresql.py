import os
import io
import boto3
import pandas as pd
import psycopg2
from psycopg2 import extras
import pyarrow.parquet as pq
from urllib.parse import unquote_plus

# Environment variables (set in Lambda configuration)
S3_BUCKET = os.environ['S3_BUCKET']
DB_NAME = os.environ['DB_NAME']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
DB_HOST = os.environ['DB_HOST']
DB_PORT = os.environ['DB_PORT']
TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    """
    This function will be invoked when a new file is placed in the S3 bucket.
    """
    try:
        # 1. Get the object key from the event
        key = unquote_plus(event['Records'][0]['s3']['object']['key'])
        print(f"Reading file: {key} from bucket: {S3_BUCKET}")

        # 2. Read Parquet file from S3 into a BytesIO object
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        parquet_file = io.BytesIO(obj['Body'].read())

        # 3. Get schema from Parquet file
        schema = pq.read_schema(parquet_file)
        columns = [(field.name, field.type) for field in schema]

        # 4. Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()

        # 5. Check if the table exists and create if not
        create_table_if_not_exists(conn, cursor, columns)

        # 6. Read data into a Pandas DataFrame for insertion
        parquet_file.seek(0)  # Reset BytesIO object position
        df = pq.read_table(parquet_file).to_pandas()

        # 7. Check for existing data and insert new records
        insert_records(conn, cursor, df)

        # 8. Commit the changes and close the connection
        conn.commit()
        cursor.close()
        conn.close()

        return {
            'statusCode': 200,
            'body': 'Data loaded successfully!'
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': f'Error: {e}'
        }

def create_table_if_not_exists(conn, cursor, columns):
    """
    Check if the table exists and create it if it doesn't.
    """
    cursor.execute(f"SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = '{TABLE_NAME}')")
    table_exists = cursor.fetchone()[0]

    if not table_exists:
        print(f"Table '{TABLE_NAME}' does not exist. Creating it...")

        # Construct CREATE TABLE statement dynamically based on extracted columns
        column_definitions = []

        for name, dtype in columns:
            pg_type = map_dtype_to_pg(dtype)  # Function to map Arrow types to PostgreSQL types
            column_definitions.append(f"{name} {pg_type}")

        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({', '.join(column_definitions)});
        """

        cursor.execute(create_table_query)
        conn.commit()
        print(f"Table '{TABLE_NAME}' created successfully.")
    else:
        print(f"Table '{TABLE_NAME}' already exists.")

def map_dtype_to_pg(arrow_type):
    """
    Map Arrow data types to PostgreSQL data types.
    """
    if arrow_type == 'int64':
        return 'BIGINT'
    elif arrow_type == 'int32':
        return 'INTEGER'
    elif arrow_type == 'float64':
        return 'DOUBLE PRECISION'
    elif arrow_type == 'float32':
        return 'REAL'
    elif arrow_type == 'string':
        return 'TEXT'
    elif arrow_type == 'boolean':
        return 'BOOLEAN'
    else:
        return 'TEXT'  # Default type

def insert_records(conn, cursor, df):
    """
    Insert records into PostgreSQL, skipping duplicates.
    """
    columns = df.columns.tolist()

    # Create a unique identifier for each record (e.g., by concatenating values from key columns)
    df['record_id'] = df.apply(lambda row: '_'.join(row.astype(str)), axis=1)

    record_ids = df['record_id'].tolist()

    # Check which record_ids already exist in the database
    cursor.execute(
        f"SELECT record_id FROM {TABLE_NAME} WHERE record_id IN %s",
        (tuple(record_ids),)
    )

    existing_ids = [row[0] for row in cursor.fetchall()]

    # Filter out records that already exist
    new_df = df[~df['record_id'].isin(existing_ids)]

    if new_df.empty:
        print("No new data to insert.")
        return

    # Prepare the data for insertion
    values = [tuple(row) for row in new_df[columns].to_numpy()]

    # Construct the SQL query
    cols = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))

    query = f"INSERT INTO {TABLE_NAME} ({cols}) VALUES %s"

    # Execute the query using execute_batch
    extras.execute_batch(cursor, query, values)

    print(f"Inserted {len(new_df)} new records.")
