# Designacao de Gestores

Sistema Django para automatizar o calculo do Modulo de Gestao e o processo de designacao de gestores escolares.

## Requisitos

- Docker Desktop 26+
- Docker Compose v2+

## Configuracao inicial

1. Copie o arquivo de exemplo de variaveis de ambiente:

   ```bash
   cp .env.example .env
   ```

   No Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Ajuste as variaveis do arquivo `.env` conforme necessidade.

## Build e execucao com Docker

1. Suba os servicos:

   ```bash
   docker compose up --build
   ```

2. Em outro terminal, aplique as migracoes:

   ```bash
   docker compose exec web python manage.py migrate
   ```

3. Crie um superusuario para acessar o admin:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

4. Acesse a aplicacao:

- App: <http://localhost:8000>
- Admin: <http://localhost:8000/admin>

## Comandos uteis

- Parar os servicos:

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

- `config/`: configuracao principal do Django (settings, urls, wsgi, asgi)
- `app/`: aplicacao principal com models, admin e migrations
- `docker-compose.yml`: orquestracao dos servicos web, mysql e redis
- `Dockerfile`: imagem da aplicacao Django
