# Designação de Gestores

Sistema Django para automatizar o cálculo do módulo de gestão e o processo de designação de gestores escolares.

## Requisitos

- Docker Desktop 26+
- Docker Compose v2+

## Configuração inicial

1. Copie o arquivo de exemplo de variáveis de ambiente:

   ```bash
   cp .env.example .env
   ```

   No Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Ajuste as variáveis do arquivo `.env` conforme necessidade.

## Build e execucao com Docker

1. Suba os serviços:

   ```bash
   docker compose up --build
   ```

2. Em outro terminal, aplique as migrações:

   ```bash
   docker compose exec web python manage.py migrate
   ```

3. Crie um super usuário para acessar o admin:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

4. Acesse a aplicação:

- App: <http://localhost:8000>
- Admin: <http://localhost:8000/admin>

## Comandos úteis

- Parar os serviços:

  ```bash
  docker compose down
  ```

- Parar e remover volumes (zera banco):

  ```bash
  docker compose down -v
  ```

- Rodar checks do Django:

  ```bash
  docker compose exec web python manage.py check
  ```

## Estrutura principal

- `config/`: configuração principal do Django (settings, urls, wsgi, asgi)
- `app/`: aplicacao principal com models, admin e migrations
- `docker-compose.yml`: orquestração dos serviços web, mysql e redis
- `Dockerfile`: imagem da aplicação Django
