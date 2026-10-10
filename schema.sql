-- Ativando a extensão para geração de UUIDs, padrão no Supabase
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tabela de Usuários (Técnicos)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    first_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 2. Tabela de Estoque Atual
CREATE TABLE IF NOT EXISTS inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL, -- Ex: 'Catraca Facial', 'Fonte'
    specs JSONB DEFAULT '{}'::jsonb, -- Características dinâmicas
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 3. Tabela de Histórico de Uso (Baixas no Cliente)
CREATE TABLE IF NOT EXISTS installations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    inventory_id UUID REFERENCES inventory(id) ON DELETE SET NULL,
    client_name TEXT NOT NULL,
    installation_date DATE NOT NULL,
    category_used TEXT NOT NULL,
    specs_used JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 4. Tabela de Peças Recolhidas (Retorno para a Matriz)
CREATE TABLE IF NOT EXISTS returns_to_hq (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_name TEXT NOT NULL,
    category TEXT NOT NULL,
    specs_removed JSONB NOT NULL,
    status TEXT DEFAULT 'PENDING_RETURN', -- Pode ser 'PENDING_RETURN' ou 'DISPATCHED'
    dispatched_date DATE, -- Preenchido apenas quando status muda para 'DISPATCHED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- Índices para melhorar a performance das consultas do bot
CREATE INDEX idx_inventory_user_id ON inventory(user_id);
CREATE INDEX idx_installations_user_id ON installations(user_id);
CREATE INDEX idx_returns_user_id ON returns_to_hq(user_id);
CREATE INDEX idx_returns_status ON returns_to_hq(status);
