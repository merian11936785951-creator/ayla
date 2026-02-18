/**
 * Frontend: Streamlink + backend proxycdn.py (Claro TV) - ENHANCED VERSION
 *
 * channels.json pode ter:
 * - Canais Claro (backend): { "slug": { "claroId": 230, "name": "..." } }
 * - Canais estáticos: { "slug": { "url": "...", "key": "...", "key2?", "useragent?", "authorization?", "proxy?", "resolution?" } }
 *
 * Backend (proxycdn.py) deve estar rodando: python3 proxycdn.py --serve 9000
 * Variável de ambiente: BACKEND_URL (default http://127.0.0.1:9000)
 * 
 * ENHANCED: Auto-renewal, error recovery, health checks, monitoring
 */

const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:9000';
const STREAMLINK_BIN = process.env.STREAMLINK_BIN || '/root/.local/bin/streamlink';
const PORT = parseInt(process.env.PORT || '8081', 10);

// Enhanced configuration
const CACHE_EXPIRY_MARGIN_MS = 60 * 1000; // 1 minuto de margem
const AUTO_RENEWAL_THRESHOLD_MS = 30 * 60 * 1000; // 30 minutos antes de expirar
const MAX_RETRY_ATTEMPTS = 3;
const RETRY_DELAY_MS = 2000;

let channelsPath = path.resolve(__dirname, 'channels.json');
let channels = loadChannels();
let activeStreams = new Map(); // Track active streams
let renewalInProgress = new Set(); // Prevent concurrent renewals

// Enhanced channel loading with validation
function loadChannels() {
    try {
        const data = JSON.parse(fs.readFileSync(channelsPath, 'utf8'));
        console.log(`[CACHE] Carregados ${Object.keys(data).length} canais`);
        return data;
    } catch (e) {
        console.error('[CACHE] Erro ao carregar channels.json:', e.message);
        return {};
    }
}

// Enhanced file watching with debouncing
let fileChangeTimeout = null;
fs.watch(channelsPath, (eventType, filename) => {
    if (eventType === 'change') {
        clearTimeout(fileChangeTimeout);
        fileChangeTimeout = setTimeout(() => {
            console.log('[CACHE] channels.json atualizado, recarregando...');
            channels = loadChannels();
        }, 500); // Debounce 500ms
    }
});

// Enhanced backend fetch with retry logic
async function fetchBackendStream(claroId, retryCount = 0) {
    return new Promise((resolve, reject) => {
        const url = `${BACKEND_URL}/api/stream/${claroId}`;
        const req = http.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    if (json.error) {
                        reject(new Error(json.error));
                        return;
                    }
                    if (!json.url || !json.key) {
                        reject(new Error('Backend nao retornou url ou key'));
                        return;
                    }
                    // Enhanced expiry calculation
                    const expiresAt = json.expires_at ? json.expires_at * 1000 : Date.now() + 4 * 60 * 60 * 1000;
                    console.log(`[BACKEND] Canal ${claroId} obtido com sucesso, expira em ${new Date(expiresAt).toISOString()}`);
                    resolve({ url: json.url, key: json.key, key2: json.key2 || null, expiresAt });
                } catch (e) {
                    reject(e);
                }
            });
        });
        req.on('error', (err) => {
            console.error(`[BACKEND] Erro de conexao (tentativa ${retryCount + 1}):`, err.message);
            if (retryCount < MAX_RETRY_ATTEMPTS) {
                setTimeout(() => {
                    fetchBackendStream(claroId, retryCount + 1).then(resolve).catch(reject);
                }, RETRY_DELAY_MS * (retryCount + 1));
            } else {
                reject(err);
            }
        });
        req.setTimeout(30000, () => {
            req.destroy();
            reject(new Error('Timeout ao chamar backend'));
        });
    });
}

// Enhanced cache validation
function isCachedClaroValid(channel) {
    if (!channel.url || !channel.key) return false;
    if (channel.keyExpiry == null) return false;
    
    const now = Date.now();
    const expiresAt = channel.keyExpiry;
    
    // Check if expired or close to expiring
    if (expiresAt <= now + CACHE_EXPIRY_MARGIN_MS) {
        console.log(`[CACHE] Canal expirou ou próximo de expirar (${new Date(expiresAt).toISOString()})`);
        return false;
    }
    
    // Check if should auto-renew
    if (expiresAt <= now + AUTO_RENEWAL_THRESHOLD_MS) {
        console.log(`[CACHE] Canal próximo da renovação automática (${new Date(expiresAt).toISOString()})`);
        return false; // Force renewal
    }
    
    return true;
}

// Enhanced cache saving with backup
function saveClaroCache(channelName, data, baseChannel) {
    try {
        // Create backup before saving
        if (fs.existsSync(channelsPath)) {
            const backupPath = channelsPath + '.backup';
            fs.copyFileSync(channelsPath, backupPath);
        }
        
        const ch = loadChannels();
        const existing = ch[channelName] || baseChannel || {};
        
        // Enhanced key extraction
        const keyOnly = data.key.includes(':') ? data.key.split(':')[1] : data.key;
        const key2Only = data.key2 && data.key2.includes(':') ? data.key2.split(':')[1] : data.key2;
        
        ch[channelName] = { 
            ...existing, 
            url: data.url, 
            key: keyOnly, 
            key2: key2Only || null, 
            keyExpiry: data.expiresAt,
            lastUpdated: Date.now()
        };
        
        fs.writeFileSync(channelsPath, JSON.stringify(ch, null, 2), 'utf8');
        channels = ch;
        console.log(`[CACHE] Cache salvo para ${channelName} (expira em ${new Date(data.expiresAt).toISOString()})`);
    } catch (e) {
        console.error('[CACHE] Erro ao salvar cache:', e.message);
    }
}

// Enhanced streamlink with better error handling
function startStreamlink(channel, channelName) {
    const useragent = channel.useragent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
    const authorization = channel.authorization;
    const proxy = channel.proxy;
    const key = channel.key;
    const key2 = channel.key2;
    let resolution = channel.resolution || 'best';

    const args = [
        '--http-header', `User-Agent=${useragent}`,
        channel.url, resolution,
        '--ffmpeg-fout', 'mpegts',
        '-O'
    ];
    
    if (authorization) {
        args.splice(2, 0, '--http-header', `Authorization=${authorization}`);
    }
    if (proxy) {
        args.splice(2, 0, '--http-proxy', proxy);
    }
    
    let keyIndex = -1;
    if (key) {
        keyIndex = args.indexOf(resolution) + 1;
        args.splice(keyIndex, 0, '-decryption_key', key);
    }
    if (key2 && keyIndex >= 0) {
        args.splice(keyIndex + 2, 0, '-decryption_key_2', key2);
    }

    console.log(`[STREAMLINK] Iniciando com args: ${args.join(' ')}`);
    const process = spawn(STREAMLINK_BIN, args);
    
    // Track active stream
    activeStreams.set(channelName, process);
    
    return process;
}

// Auto-renewal system
async function autoRenewChannel(channelName, channel) {
    if (renewalInProgress.has(channelName)) {
        console.log(`[RENEWAL] Renovação já em andamento para ${channelName}`);
        return;
    }
    
    renewalInProgress.add(channelName);
    
    try {
        console.log(`[RENEWAL] Iniciando renovação automática para ${channelName}`);
        const backend = await fetchBackendStream(String(channel.claroId));
        saveClaroCache(channelName, { 
            url: backend.url, 
            key: backend.key, 
            key2: backend.key2, 
            expiresAt: backend.expiresAt 
        }, { claroId: channel.claroId, name: channel.name });
        console.log(`[RENEWAL] Renovação concluída com sucesso para ${channelName}`);
    } catch (e) {
        console.error(`[RENEWAL] Falha na renovação para ${channelName}:`, e.message);
    } finally {
        renewalInProgress.delete(channelName);
    }
}

// Health check system
function performHealthCheck() {
    console.log('[HEALTH] Iniciando verificação de saúde...');
    
    let expiringSoon = [];
    let expired = [];
    const now = Date.now();
    
    for (const [channelName, channel] of Object.entries(channels)) {
        if (channel.keyExpiry) {
            const timeUntilExpiry = channel.keyExpiry - now;
            
            if (timeUntilExpiry <= 0) {
                expired.push({ channel: channelName, expiredAt: new Date(channel.keyExpiry).toISOString() });
            } else if (timeUntilExpiry <= AUTO_RENEWAL_THRESHOLD_MS) {
                expiringSoon.push({ channel: channelName, expiresAt: new Date(channel.keyExpiry).toISOString() });
                
                // Trigger auto-renewal
                if (channel.claroId && !renewalInProgress.has(channelName)) {
                    autoRenewChannel(channelName, channel);
                }
            }
        }
    }
    
    if (expired.length > 0) {
        console.log(`[HEALTH] Canais expirados: ${expired.map(c => c.channel).join(', ')}`);
    }
    
    if (expiringSoon.length > 0) {
        console.log(`[HEALTH] Canais expirando em breve: ${expiringSoon.map(c => c.channel).join(', ')}`);
    }
    
    if (expired.length === 0 && expiringSoon.length === 0) {
        console.log('[HEALTH] Todos os canais com cache válido');
    }
}

// Start health check interval
setInterval(performHealthCheck, 5 * 60 * 1000); // 5 minutos

const app = express();

// Enhanced middleware
app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    next();
});

// Enhanced streaming endpoint
app.get('/stream/:channelName', async (req, res) => {
    const channelName = req.params.channelName;
    console.log(`[REQUEST] Pedido /stream/${channelName}`);

    let channel = channels[channelName];
    if (!channel) {
        const claroId = /^\d+$/.test(channelName) ? parseInt(channelName, 10) : null;
        if (claroId != null) {
            channel = { claroId, name: 'Canal ' + channelName };
            channels[channelName] = channel;
            console.log(`[CACHE] Canal ${channelName} não estava em channels.json; usando claroId=${claroId} e salvando após obter dados.`);
        } else {
            res.status(404).send('Canal não encontrado. Use um ID numérico (ex: /stream/230) ou adicione o canal em channels.json');
            return;
        }
    }

    let url = channel.url;
    let key = channel.key;
    let key2 = channel.key2 || null;

    if (channel.claroId != null) {
        if (isCachedClaroValid(channel)) {
            url = channel.url;
            key = channel.key;
            key2 = channel.key2 || null;
            console.log(`[CACHE] Usando cache válido para ${channelName}`);
        } else {
            try {
                console.log(`[BACKEND] Obtendo URL e chaves do backend para claroId=${channel.claroId}`);
                const backend = await fetchBackendStream(String(channel.claroId));
                url = backend.url;
                key = backend.key;
                key2 = backend.key2;
                saveClaroCache(channelName, { url, key, key2, expiresAt: backend.expiresAt }, { claroId: channel.claroId, name: channel.name });
            } catch (e) {
                console.error(`[BACKEND] Erro: ${e.message}`);
                
                // Try to use expired cache as fallback
                if (channel.url && channel.key) {
                    console.log(`[FALLBACK] Usando cache expirado como fallback para ${channelName}`);
                    url = channel.url;
                    key = channel.key;
                    key2 = channel.key2;
                } else {
                    res.status(502).send('Backend indisponível ou erro: ' + e.message);
                    return;
                }
            }
        }
    }

    const streamChannel = { ...channel, url, key, key2 };

    if (!url || !key) {
        res.status(500).send('Canal sem url ou chave (verifique backend para claroId)');
        return;
    }

    console.log(`[STREAM] Iniciando Streamlink para ${channelName}`);
    try {
        const streamlinkProcess = startStreamlink(streamChannel, channelName);
        res.setHeader('Content-Type', 'video/MP2T');
        streamlinkProcess.stdout.pipe(res);

        streamlinkProcess.stderr.on('data', data => {
            const output = data.toString().trim();
            if (output.includes('error') || output.includes('Error')) {
                console.error(`[STREAMLINK] Error: ${output}`);
            } else {
                console.log(`[STREAMLINK] ${output}`);
            }
        });
        
        streamlinkProcess.on('close', code => {
            console.log(`[STREAM] Streamlink encerrado com código ${code} para ${channelName}`);
            activeStreams.delete(channelName);
            if (!res.writableEnded) res.end();
        });
        
        res.on('close', () => {
            console.log(`[CLIENT] Cliente fechou conexão para ${channelName}`);
            streamlinkProcess.kill();
            activeStreams.delete(channelName);
        });
        
        req.on('abort', () => {
            streamlinkProcess.kill();
            activeStreams.delete(channelName);
        });
    } catch (err) {
        console.error(`[STREAM] Streamlink falhou para ${channelName}:`, err);
        res.status(500).send('Streamlink falhou');
    }
});

// Enhanced health endpoint
app.get('/health', (req, res) => {
    const now = Date.now();
    const channelStatus = {};
    
    for (const [name, channel] of Object.entries(channels)) {
        const status = {
            hasCache: !!(channel.url && channel.key),
            keyExpiry: channel.keyExpiry ? new Date(channel.keyExpiry).toISOString() : null,
            timeUntilExpiry: channel.keyExpiry ? Math.max(0, channel.keyExpiry - now) : null,
            isActive: activeStreams.has(name),
            claroId: channel.claroId || null
        };
        channelStatus[name] = status;
    }
    
    res.json({ 
        ok: true, 
        channels: Object.keys(channels).length,
        activeStreams: activeStreams.size,
        renewalInProgress: renewalInProgress.size,
        timestamp: new Date().toISOString(),
        channelStatus
    });
});

// Status endpoint for monitoring
app.get('/status', (req, res) => {
    res.json({
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        activeStreams: Array.from(activeStreams.keys()),
        renewalInProgress: Array.from(renewalInProgress),
        backendUrl: BACKEND_URL,
        streamlinkBin: STREAMLINK_BIN
    });
});

// Manual renewal endpoint
app.post('/renew/:channelName', async (req, res) => {
    const channelName = req.params.channelName;
    const channel = channels[channelName];
    
    if (!channel || !channel.claroId) {
        res.status(404).send('Canal não encontrado ou não é um canal Claro');
        return;
    }
    
    try {
        console.log(`[MANUAL] Renovação manual solicitada para ${channelName}`);
        const backend = await fetchBackendStream(String(channel.claroId));
        saveClaroCache(channelName, { url: backend.url, key: backend.key, key2: backend.key2, expiresAt: backend.expiresAt }, channel);
        res.json({ success: true, message: `Canal ${channelName} renovado com sucesso`, expiresAt: new Date(backend.expiresAt).toISOString() });
    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
    console.log(`[SERVER] Frontend rodando em http://0.0.0.0:${PORT}`);
    console.log(`[SERVER] Backend esperado em ${BACKEND_URL}`);
    console.log(`[SERVER] Exemplo: http://127.0.0.1:${PORT}/stream/230`);
    console.log(`[SERVER] Health check: http://127.0.0.1:${PORT}/health`);
    console.log(`[SERVER] Status: http://127.0.0.1:${PORT}/status`);
    
    // Perform initial health check
    setTimeout(performHealthCheck, 5000);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('[SHUTDOWN] Encerrando servidor...');
    
    // Kill all active streams
    for (const [name, process] of activeStreams) {
        console.log(`[SHUTDOWN] Encerrando stream ${name}`);
        process.kill();
    }
    
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('[SHUTDOWN] Recebido SIGTERM');
    process.exit(0);
});
