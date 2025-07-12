# Spotify to YouTube Music Transfer Tool

*Proyecto con modificaciones personales del original. Creador original: @sigma67*

Una herramienta de línea de comandos para transferir playlists de Spotify a YouTube Music con funcionalidades avanzadas de sincronización y gestión.

## 🚀 Instalación

```bash
pip install -e .
```

## ⚙️ Configuración Inicial

Antes de usar la herramienta, necesitas configurar las credenciales:

```bash
spotify_to_ytmusic_v2 setup
```

Este comando te guiará para configurar:
- Credenciales de Spotify (OAuth o Client ID/Secret)
- Autenticación de YouTube Music (navegador o OAuth)

## 📚 Comandos Disponibles

### 🔧 Setup y Configuración

#### `setup`
Configura las credenciales de Spotify y YouTube Music.

```bash
spotify_to_ytmusic_v2 setup [--file PATH]
```

**Opciones:**
- `--file`: Ruta opcional a un archivo settings.ini personalizado

#### `logs-location`
Muestra la ubicación de los archivos de log y credenciales.

```bash
spotify_to_ytmusic_v2 logs-location
```

### 📋 Transferencia de Playlists

#### `create`
Crea una nueva playlist en YouTube Music desde una playlist de Spotify.

```bash
spotify_to_ytmusic_v2 create PLAYLIST_URL [opciones]
```

**Parámetros requeridos:**
- `PLAYLIST_URL`: Link de la playlist de Spotify

**Opciones:**
- `-n, --name`: Nombre personalizado para la playlist (por defecto: nombre original)
- `-i, --info`: Descripción personalizada (por defecto: descripción original)
- `-d, --date`: Agregar la fecha actual al nombre de la playlist
- `-p, --public`: Hacer la playlist pública (por defecto: privada)
- `-l, --like`: Dar "me gusta" a todas las canciones transferidas
- `--use-cached`: Usar cache para acelerar búsquedas

**Ejemplo:**
```bash
spotify_to_ytmusic_v2 create "https://open.spotify.com/playlist/..." --name "Mi Playlist" --public --like
```

#### `update`
Actualiza una playlist existente en YouTube Music eliminando todo el contenido y agregando las canciones de Spotify.

```bash
spotify_to_ytmusic_v2 update PLAYLIST_URL PLAYLIST_NAME [opciones]
```

**Parámetros requeridos:**
- `PLAYLIST_URL`: Link de la playlist de Spotify
- `PLAYLIST_NAME`: Nombre de la playlist en YouTube Music a actualizar

**Opciones:**
- `--append`: No eliminar canciones existentes, solo agregar las nuevas
- `--use-cached`: Usar cache para búsquedas

#### `liked`
Transfiere todas las canciones que te gustan de Spotify a YouTube Music.

```bash
spotify_to_ytmusic_v2 liked [opciones]
```

**Opciones:**
- `-n, --name`: Nombre para la playlist (por defecto: "Spotify Liked Songs")
- `-i, --info`: Descripción para la playlist
- `-d, --date`: Agregar fecha al nombre
- `-p, --public`: Hacer la playlist pública
- `-l, --like`: Dar "me gusta" a las canciones
- `--use-cached`: Usar cache

### 📁 Transferencia Masiva

#### `all`
Transfiere todas las playlists públicas de un usuario de Spotify.

```bash
spotify_to_ytmusic_v2 all USER_ID [opciones]
```

**Parámetros requeridos:**
- `USER_ID`: ID del usuario de Spotify

**Opciones:**
- `-l, --like`: Dar "me gusta" a todas las canciones
- `--use-cached`: Usar cache

#### `all-saved`
Transfiere todo el contenido guardado de tu biblioteca de Spotify (playlists y álbumes).

```bash
spotify_to_ytmusic_v2 all-saved [opciones]
```

**Opciones:**
- `--target-user`: Incluir también playlists públicas de este usuario de Spotify
- `--batch-size`: Número de playlists a procesar antes de pausar (por defecto: 5)
- `--batch-delay`: Segundos de espera entre lotes (por defecto: 2)
- `-n, --name`: Prefijo para nombres de playlists
- `-i, --info`: Descripción para playlists
- `-d, --date`: Agregar fecha
- `-p, --public`: Hacer playlists públicas
- `-l, --like`: Dar "me gusta" a canciones
- `--use-cached`: Usar cache

#### `update-all`
Compara y actualiza todas las playlists y álbumes guardados entre Spotify y YouTube Music.

```bash
spotify_to_ytmusic_v2 update-all [opciones]
```

**Opciones:**
- `--target-user`: Incluir playlists públicas de este usuario
- `--batch-size`: Playlists por lote (por defecto: 5)
- `--batch-delay`: Segundos entre lotes (por defecto: 2)
- `--append`: No eliminar canciones, solo agregar las faltantes
- `--tolerance`: Ratio mínimo de coincidencia para considerar playlist actualizada (por defecto: 0.9 = 90%)
- `--use-cached`: Usar cache

#### `initial-setup`
Escanea playlists existentes en YouTube Music y las registra en los logs para seguimiento.

```bash
spotify_to_ytmusic_v2 initial-setup [opciones]
```

**Opciones:**
- `--target-user`: Escanear también playlists que coincidan con playlists públicas de este usuario de Spotify
- `--use-cached`: Usar cache

### 🔍 Utilidades

#### `search`
Busca una canción específica en YouTube Music para verificar el algoritmo de coincidencia.

```bash
spotify_to_ytmusic_v2 search SONG_LINK [opciones]
```

**Parámetros requeridos:**
- `SONG_LINK`: Link de la canción de Spotify

**Opciones:**
- `--use-cached`: Usar cache

#### `remove`
Elimina playlists que coincidan con un patrón regex específico.

```bash
spotify_to_ytmusic_v2 remove PATTERN
```

**Parámetros requeridos:**
- `PATTERN`: Patrón regex para identificar playlists a eliminar

### 📊 Gestión de Cache y Logs

#### `cache-clear`
Limpia el archivo de cache.

```bash
spotify_to_ytmusic_v2 cache-clear
```

#### `log-stats`
Muestra estadísticas de las operaciones de playlists registradas en los logs.

```bash
spotify_to_ytmusic_v2 log-stats
```

### 🆘 Información del Sistema

#### `--version`, `-v`
Muestra las versiones de los componentes instalados.

```bash
spotify_to_ytmusic_v2 --version
```

## 🎯 Ejemplos de Uso Común

### Transferir una playlist específica
```bash
spotify_to_ytmusic_v2 create "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd" --name "Top Hits" --public
```

### Sincronizar todas tus playlists guardadas
```bash
spotify_to_ytmusic_v2 all-saved --batch-size 3 --batch-delay 5
```

### Actualizar una playlist existente
```bash
spotify_to_ytmusic_v2 update "https://open.spotify.com/playlist/..." "Mi Playlist Actualizada" --append
```

### Transferir canciones favoritas
```bash
spotify_to_ytmusic_v2 liked --name "Mis Favoritas de Spotify" --like
```

## 📁 Archivos de Configuración

La herramienta almacena la configuración y logs en:
- **Configuración**: `~/.cache/spotify_to_ytmusic/settings.ini`
- **Cache de Spotify**: `~/.cache/spotify_to_ytmusic/spotipy.cache`
- **Log de operaciones**: `~/.cache/spotify_to_ytmusic/backup_log.jsonl`
- **Canciones no encontradas**: `~/.cache/spotify_to_ytmusic/noresults_youtube.txt`

Usa `spotify_to_ytmusic_v2 logs-location` para ver las rutas exactas en tu sistema.

## ⚡ Funcionalidades Avanzadas

### Sistema de Cache
- Usa `--use-cached` para acelerar búsquedas repetidas
- Las búsquedas se almacenan en `lookup.json`
- Limpia el cache con `cache-clear` si es necesario

### Procesamiento por Lotes
- Los comandos `all-saved` y `update-all` procesan en lotes para evitar límites de API
- Configura `--batch-size` y `--batch-delay` según tus necesidades

### Algoritmo de Coincidencia
- Coincidencia difusa basada en título, artista y duración
- Tolerancia de ±2 segundos para duración
- Sistema de puntuación ponderado que favorece coincidencias exactas

## 🔑 Autenticación

### Spotify
- **OAuth**: Para playlists privadas y canciones favoritas
- **Client Credentials**: Para playlists públicas

### YouTube Music
- **Navegador**: Recomendado, más estable
- **OAuth**: Para integración programática

## 📝 Notas Importantes

- Las playlists se crean como **privadas** por defecto (usa `-p` para públicas)
- Las canciones no encontradas se registran en `noresults_youtube.txt`
- Los errores de autenticación muestran instrucciones de configuración
- Todas las operaciones se registran para seguimiento y recuperación