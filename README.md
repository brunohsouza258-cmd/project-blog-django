# Blog

Blog pessoal feito com **Django** e **Docker**, com sistema de contas, página de feedback e um assistente de **IA local** que responde dúvidas dos visitantes sobre o blog.

> 🤖 **Feito com IA**: este projeto foi desenvolvido com a ajuda do [Claude Code](https://claude.com/claude-code), assistente de programação da Anthropic. A IA ajudou a escrever o código, os testes, o visual e as configurações de segurança, sempre com revisão e direção minhas.

## O que o blog faz

- **Página inicial** com layout moderno, tema claro/escuro automático e versão para celular.
- **Configuração pelo admin**: título, descrição, favicon, links do menu e quais partes do site aparecem (header, busca, menu, rodapé...) são editados no painel, sem mexer no código.
- **Contas de usuário**: o visitante cria uma conta com nome, e-mail e senha, e entra com o e-mail. O dono do blog recebe um aviso por e-mail a cada novo cadastro.
- **Feedback**: formulário para elogios, sugestões e problemas. As mensagens ficam salvas no admin (com marcação de "lido") e também são enviadas por e-mail.
- **Assistente com IA local**: um chat flutuante, em todas as páginas, que responde **somente** sobre o blog (autor, contato, como criar conta, etc.). A IA roda no próprio computador com [Ollama](https://ollama.com), sem enviar as conversas para serviços externos.

## Segurança

- Limite de tentativas por IP no login (contra força bruta), no cadastro, no feedback e no chat.
- Armadilha invisível (honeypot) contra robôs de spam no feedback.
- Content Security Policy, cookies `HttpOnly`/`Secure` e HTTPS obrigatório em produção.
- Validação contra injeção em cabeçalhos de e-mail e contra links `javascript:` no menu.
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

### Testes

```bash
docker compose exec djangoapp python manage.py test
```

## Estrutura

```
djangoapp/
├── blog/         # páginas, templates e CSS do site
├── site_setup/   # configurações do site editáveis pelo admin
├── accounts/     # cadastro, login e logout
├── feedback/     # formulário de feedback
├── chatbot/      # assistente com IA local
└── utils/        # imagens, validadores e limitador de tentativas
```

## Autor

Feito por **Bruno** com a ajuda de IA. Contato: [Bruno.h.souza258@gmail.com](mailto:Bruno.h.souza258@gmail.com)
