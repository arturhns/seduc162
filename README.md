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

## Build e execução com Docker

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

## Testes

Os testes automatizados ficam em `app/tests/` (por exemplo `app/tests/test_calculo_modulo.py`) e usam o runner do Django com banco de dados. Com os serviços em execução (`docker compose up`), rode-os **dentro do container** `web` para que o host do MySQL (`mysql` no Compose) esteja resolvido corretamente.

- Toda a suíte da aplicação `app`:

  ```bash
  docker compose exec web python manage.py test app
  ```

- Apenas o pacote de testes:

  ```bash
  docker compose exec web python manage.py test app.tests
  ```

- Um arquivo ou caso específico (ajuste o caminho conforme o teste):

  ```bash
  docker compose exec web python manage.py test app.tests.test_calculo_modulo
  docker compose exec web python manage.py test app.tests.test_calculo_modulo.CalculoModuloServiceTestCase
  ```

- Mais detalhe na saída (níveis 0–3):

  ```bash
  docker compose exec web python manage.py test app -v 2
  ```

Se desenvolver **fora do Docker**, use o mesmo comando `python manage.py test ...` no ambiente virtual, com `.env` apontando `DATABASE_HOST` (e demais variáveis) para a instância MySQL acessível da sua máquina.

## Estrutura principal

- `config/`: configuração principal do Django (settings, urls, wsgi, asgi)
- `app/`: aplicação principal com models, admin e migrations
- `docker-compose.yml`: orquestração dos serviços web, mysql e redis
- `Dockerfile`: imagem da aplicação Django
