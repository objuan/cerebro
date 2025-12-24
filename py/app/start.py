import asyncio
import sys
import os

from webapp import app  # Importa la tua app FastAPI

if __name__ == "__main__":
    if sys.platform == 'win32':
        # 1. Forza la policy del SelectorLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn
    
    # 2. Crea manualmente il loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    print(f"Loop creato manualmente: {type(loop).__name__}")

    #os.chdir("APP")

    '''
    uvicorn.run(
        "webapp:app",
        host="127.0.0.1",
        port=8000,
        reload=True,          # ✅ reload attivo
        loop="asyncio",
        log_level="info",
    )
    '''
    
    # 3. Configura Uvicorn per usare questo loop specifico
    config = uvicorn.Config(
        app=app, 
        loop="asyncio", 
        host="127.0.0.1", 
        port=8080,
        log_level="info",
    )
    server = uvicorn.Server(config)
    
    # 4. Esegui il server nel loop che abbiamo creato
    loop.run_until_complete(server.serve())
    
    