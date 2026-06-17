1. Start a Chroma-DB container.
2. Run ingest.py script manually, which will consume all data, chunk it, and create embeddings using open-ai embedding, and then store it in the Chroma-DB container.
3. Run the app.py script which will start a flask server. You can then send a POST request to the /ask endpoint . The server will return the most relevant chunks from the Chroma-DB based on the query.
4. Send retrieved chunks to the open-ai API to get a response based on the retrieved chunks. The response will be returned to the user.