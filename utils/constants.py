FLASHCARDS_RESPONSE_TEMPLATE = {
  "flashcards": [
        {
            "question": "conteúdo da pergunta contendo no máximo 100 caracteres",
            "answer": "conteúdo da respostas contendo no máximo 100 caracteres",
            "opened": False
        }
  ]
}

USER_LIMITS = {
    0: {
        "daily_flashcards_limit": 50,
        "daily_ai_gen_flashcards_limit": 5,
        "daily_subjects_limit": 5
    },
    1: {
        "daily_flashcards_limit": 1000,
        "daily_ai_gen_flashcards_limit": 100,
        "daily_subjects_limit": 1000
    }
}

CREDIT_PACKAGES = [
    # Pacotes pequenos (para testes ou usuários casuais)
    {"id": 1, "credits": 50, "price": 2.99, "description": "Pacote teste", "best_value": False},
    {"id": 2, "credits": 100, "price": 4.99, "description": "Pacote básico", "best_value": False},
    
    # Pacotes médios (usuários regulares)
    {"id": 3, "credits": 300, "price": 12.99, "description": "Pacote médio", "best_value": True},
    {"id": 4, "credits": 600, "price": 19.99, "description": "Pacote avançado", "best_value": False},
    
    # Pacotes grandes (usuários frequentes - com desconto progressivo)
    {"id": 5, "credits": 1000, "price": 29.99, "description": "Pacote grande", "best_value": True},
    {"id": 6, "credits": 2500, "price": 59.99, "description": "Pacote premium", "best_value": False},
    {"id": 7, "credits": 5000, "price": 99.99, "description": "Pacote máster", "best_value": True},
    
    # Pacote especial (melhor custo-benefício)
    {"id": 8, "credits": 10000, "price": 149.99, "description": "Pacote anual", "best_value": True}
]