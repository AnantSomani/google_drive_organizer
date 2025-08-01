# Google Drive Organizer

AI-powered Google Drive file organization tool that automatically categorizes and structures your files using intelligent classification.

## Features

- 🔐 Secure OAuth authentication with Google Drive
- 🤖 AI-powered file classification and organization
- 📊 Interactive tree visualization of proposed structure
- ↩️ Undo functionality with audit trail
- ⚙️ Customizable preferences and filters
- 🚀 Real-time processing with background tasks

## Tech Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.12
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth with Google OAuth
- **AI**: OpenAI GPT-4 for classification
- **Deployment**: Vercel (Frontend), Railway (Backend)

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.12+
- pnpm
- Poetry

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pnpm setup
   ```
3. Set up environment variables (see `.env.example`)
4. Run the development servers:
   ```bash
   pnpm dev
   ```

## Development

- `pnpm dev` - Start both frontend and backend in development mode
- `pnpm test` - Run all tests
- `pnpm lint` - Run linting
- `pnpm build` - Build for production

## License

MIT License - see [LICENSE](LICENSE) for details. 