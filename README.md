# Blog

Blog pessoal feito com **Django** e **Docker**, com sistema de contas, página de feedback e um assistente de **IA local** que responde dúvidas dos visitantes sobre o blog.

> 🤖 **Feito com IA**: este projeto foi desenvolvido com a ajuda do [Claude Code](https://claude.com/claude-code), assistente de programação da Anthropic. A IA ajudou a escrever o código, os testes, o visual e as configurações de segurança, sempre com revisão e direção minhas.

## O que o blog faz

- **Posts** escritos pelo painel admin: aparecem na hora na página inicial, com paginação, página própria, categorias, posts relacionados, tempo de leitura e capa. Rascunhos ficam visíveis só para o admin e posts com data futura são publicados automaticamente na data marcada.
- **Busca** em português que entende variações das palavras ("programar" encontra "programação").
- **Feed RSS** em `/feed/` para os leitores acompanharem os posts novos.
- **Página inicial** com layout moderno, tema claro/escuro automático e versão para celular.
- **Configuração pelo admin**: título, descrição, favicon, links do menu e quais partes do site aparecem (header, busca, menu, rodapé...) são editados no painel, sem mexer no código.
- **Contas de usuário**: o visitante cria uma conta com nome, e-mail e senha, e entra com o e-mail. O dono do blog recebe um aviso por e-mail a cada novo cadastro.
- **Feedback**: formulário para elogios, sugestões e problemas. As mensagens ficam salvas no admin (com marcação de "lido") e também são enviadas por e-mail.
- **Assistente com IA local**: um chat flutuante, em todas as páginas, que responde **somente** sobre o blog (posts, autor, contato, como criar conta, etc.). A cada pergunta ele consulta os posts publicados mais recentes e os mais relacionados ao assunto, então conhece um post novo assim que ele é publicado, e responde com links clicáveis para os posts. A IA roda no próprio computador com [Ollama](https://ollama.com), sem enviar as conversas para serviços externos.

## Segurança

- Limite de tentativas por IP no login do site e do admin (contra força bruta), no cadastro, no feedback e no chat. Os contadores ficam no banco e não zeram ao reiniciar.
- Endereço do painel admin configurável (`ADMIN_URL`), para não ficar no óbvio `/admin/`.
- Armadilha invisível (honeypot) contra robôs de spam no feedback.
- Content Security Policy, cookies `HttpOnly`/`Secure` e HTTPS obrigatório em produção.
- Validação contra injeção em cabeçalhos de e-mail e contra links `javascript:` no menu.
- Conteúdo dos posts e respostas da IA sempre exibidos como texto (sem HTML); no chat, só links do próprio blog ficam clicáveis.
- Banco de dados e IA acessíveis apenas dentro do Docker.

## Tecnologias

| Parte | Tecnologia |
|---|---|
| Back-end | Python 3.13, Django 6.1 |
| Banco de dados | PostgreSQL 16 |
| IA local | Ollama + modelo Qwen 2.5 (3B) |
| Front-end | HTML, CSS e JavaScript puros (sem frameworks) |
| Infraestrutura | Docker e Docker Compose |

## Como rodar

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e aberto.

1. Copie o arquivo de exemplo de variáveis de ambiente e preencha os valores `CHANGE-ME`:

   ```bash
   cp dotenv_files/.env-exemplo dotenv_files/.env
   ```

2. Suba os containers:

   ```bash
   docker compose up -d --build
   ```

3. Baixe o modelo de IA (só na primeira vez, cerca de 2 GB):

   ```bash
   docker compose exec ollama ollama pull qwen2.5:3b
   ```

4. Crie um usuário administrador:

   ```bash
   docker compose exec djangoapp python manage.py createsuperuser
   ```

5. Acesse **http://localhost:8000**. O painel fica em **http://localhost:8000/admin**.

### Posts de exemplo

Para preencher o blog com 15 posts sobre personalidades famosas (esporte, música, cinema, ciência e literatura), rode:

```bash
docker compose exec djangoapp python manage.py seed_posts
```

12 posts são publicados com datas das últimas semanas e 3 ficam agendados para os próximos dias, aparecendo sozinhos no site. O comando pode ser executado mais de uma vez sem duplicar posts. O conteúdo fica em `djangoapp/blog/data/famosos.json`.

### Publicando um post

No admin, vá em **Posts → Adicionar**, preencha título, resumo e conteúdo (uma linha em branco entre parágrafos), marque **Publicado** e salve. O post aparece no site, no feed RSS e no assistente de IA na hora.

### Produção

Com `DEBUG="0"` no `.env`, o container sobe com **gunicorn** em vez do servidor de desenvolvimento, e o CSS/JS é servido comprimido e com cache pelo WhiteNoise. Antes de publicar, configure no `.env`:

| Variável | Para quê |
|---|---|
| `SECRET_KEY` | Chave longa e aleatória |
| `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | Domínio do site (ex.: `meublog.com` / `https://meublog.com`) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Usuário do banco sem poderes de superusuário e senha forte |
| `ADMIN_URL` | Endereço secreto do painel (ex.: `painel-xk29fm/`) |
| `NUM_PROXIES` | `1` se houver um nginx na frente do Django, para identificar o IP real dos visitantes |

O site precisa de HTTPS em produção: os cookies de login só trafegam por conexão segura.

### Mostrar para amigos (link público)

Para outras pessoas acessarem o blog pela internet enquanto seu computador estiver ligado, use o modo público. Ele roda o site em modo produção e cria um link `https://xxxx.trycloudflare.com` com um túnel gratuito da Cloudflare, sem abrir portas no roteador e sem criar conta:

```bash
docker compose -f docker-compose.yml -f docker-compose.publico.yml up -d
docker compose -f docker-compose.yml -f docker-compose.publico.yml logs tunnel   # mostra o link
```

O link muda sempre que o túnel reinicia. Nesse modo, acesse o site pelo link (não pelo `localhost:8000`). Para voltar ao modo de desenvolvimento:

```bash
docker compose rm -sf tunnel
docker compose up -d --force-recreate djangoapp
```

### Testes

```bash
docker compose exec djangoapp python manage.py test
```

## Estrutura

```
djangoapp/
├── blog/         # posts, categorias, busca, feed RSS, templates e CSS
├── site_setup/   # configurações do site editáveis pelo admin
├── accounts/     # cadastro, login e logout
├── feedback/     # formulário de feedback
├── chatbot/      # assistente com IA local
└── utils/        # imagens, validadores e limitador de tentativas
```

## Autor

Feito por **Bruno** com a ajuda de IA. Contato: [Bruno.h.souza258@gmail.com](mailto:Bruno.h.souza258@gmail.com)
