import re
import io
import logging
from typing import Optional, Dict, Any
try:
    from PIL import Image, ImageEnhance, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Palavras que frequentemente aparecem em etiquetas mas NÃO são números de série
STOP_WORDS = {
    "CONTROL", "ID", "CONTROLID", "CONTROL-ID", "INTELBRAS", "HIKVISION", "ZKTECO", "DIMEP", "WOLPAC", "HENRY",
    "MODELO", "MODEL", "MARCA", "BRAND", "PLACA", "FONTE", "ANTENA", "CATRACA", "LEITOR",
    "MADE", "IN", "BRAZIL", "BRASIL", "INDUSTRIA", "BRASILEIRA", "ANATEL", "CNPJ", "HOMOLOGACAO",
    "ALIMENTACAO", "ENTRADA", "SAIDA", "INPUT", "OUTPUT", "VOLTS", "AMPERES", "VOLT", "AMPERE",
    "REV", "VERSAO", "VERSION", "LOTE", "BATCH", "FAB", "SERIE", "SERIAL", "CODIGO", "CODE",
    "WWW", "COM", "BR", "SAC", "TEL", "DATA", "DATE", "EQUIPAMENTO", "PRODUTO", "TERMINAL"
}

# Modelos conhecidos comuns no mercado para identificação precisa
KNOWN_MODELS = {
    "IDFACE MAX": "iDFace Max",
    "IDFACE INOX": "iDFace Inox",
    "IDFACE": "iDFace",
    "IDBLOCK": "iDBlock",
    "IDBOX": "iDBox",
    "IDFLEX": "iDFlex",
    "IDCLASS": "iDClass",
    "IDLOCK": "iDLock",
    "IDTOUCH": "iDTouch",
    "IDFIT": "iDFit",
    "IDPROX": "iDProx",
    "IDUHF": "iDUHF",
    "IDBAR": "iDBar",
    "SS 3530 MF": "SS 3530 MF",
    "SS 3540 MF": "SS 3540 MF",
    "SS 3542 MF": "SS 3542 MF",
    "SS 3530": "SS 3530",
    "SS 3540": "SS 3540",
    "FACE 3000": "Face 3000",
    "DS-K1T341": "DS-K1T341",
    "DS-K1T671": "DS-K1T671",
    "DS-K1T342": "DS-K1T342"
}

def preprocess_image(image: Image.Image) -> Image.Image:
    """Aplica escala de cinza e realce de contraste para melhor leitura de etiquetas."""
    gray = image.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)
    return enhanced

def extract_text_from_bytes(image_bytes: bytes) -> str:
    """Extrai texto bruto de uma imagem em bytes usando Tesseract OCR com múltiplos modos."""
    if not PYTESSERACT_AVAILABLE or not PIL_AVAILABLE:
        logger.error("Pytesseract ou Pillow (PIL) NÃO estão disponíveis no ambiente!")
        return ""

    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Corrige orientação EXIF comum em fotos tiradas por smartphones
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        logger.info(f"Processando imagem para OCR (formato: {image.format}, tamanho: {image.size})")

        extracted_texts = []

        # 1. Passada padrão com português e inglês
        try:
            t1 = pytesseract.image_to_string(image, lang='por+eng').strip()
            if t1:
                extracted_texts.append(t1)
        except Exception as e:
            logger.warning(f"Passada 1 OCR falhou: {e}")

        # 2. Passada com pré-processamento de contraste e PSM 6 (bloco de texto uniforme)
        try:
            processed = preprocess_image(image)
            t2 = pytesseract.image_to_string(processed, lang='por+eng', config='--psm 6').strip()
            if t2 and t2 not in extracted_texts:
                extracted_texts.append(t2)
        except Exception as e:
            logger.warning(f"Passada 2 OCR falhou: {e}")

        # 3. Passada com PSM 11 (texto esparso - excelente para números de série ou códigos isolados)
        try:
            processed = preprocess_image(image)
            t3 = pytesseract.image_to_string(processed, lang='eng', config='--psm 11').strip()
            if t3 and t3 not in extracted_texts:
                extracted_texts.append(t3)
        except Exception as e:
            logger.warning(f"Passada 3 OCR falhou: {e}")

        # Combina os textos reconhecidos para não perder nenhum dado
        combined_text = "\n".join(extracted_texts).strip()
        logger.info(f"Texto extraído pelo OCR ({len(combined_text)} caracteres): {repr(combined_text)}")
        return combined_text
    except Exception as e:
        logger.exception(f"Erro ao processar OCR da imagem: {e}")
        return ""

def clean_token(token: str) -> str:
    """Remove pontuações e caracteres de borda comuns em códigos de barra ou ruídos de OCR."""
    return re.sub(r'^[\s\*\:\|\.\-\_\#\(\)\[\]\\\/]+|[\s\*\:\|\.\-\_\#\(\)\[\]\\\/]+$', '', token)

def is_blacklisted(token: str, mac_cleaned: Optional[str] = None) -> bool:
    """Verifica se um token definitivamente não é um número de série de equipamento."""
    cleaned = clean_token(token).upper()
    if not cleaned or len(cleaned) < 4:
        return True

    if cleaned in STOP_WORDS:
        return True

    # Se for idêntico ao MAC address
    if mac_cleaned and cleaned.replace(":", "").replace("-", "") == mac_cleaned.replace(":", "").replace("-", ""):
        return True

    # CNPJ (ex: 08.831.603/0001-77 ou 08831603000177)
    if re.search(r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}', cleaned) or (len(cleaned) == 14 and cleaned.isdigit() and cleaned.startswith("08")):
        return True

    # Código Anatel (ex: 05030-20-12965 ou 050302012965)
    if re.search(r'\d{5}-?\d{2}-?\d{5}', cleaned):
        return True

    # Padrão elétrico (ex: 12V, 24V, 2A, 12VDC, 500MA, 60HZ)
    if re.match(r'^\d+(?:\.\d+)?\s*(?:V|VDC|VCC|VAC|A|MA|W|HZ)$', cleaned):
        return True

    # Datas (ex: 01/2023, 2023-10)
    if re.search(r'\d{2}[\/\-]\d{2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{2}', cleaned):
        return True

    # Links ou emails
    if any(x in cleaned.lower() for x in [".com", ".br", "http", "@"]):
        return True

    return False

def parse_label_info(raw_text: str) -> Dict[str, Optional[str]]:
    """
    Analisa o texto extraído da etiqueta e identifica:
    - Marca (ex: Control iD, Intelbras, etc.)
    - Modelo (ex: iDFace, iDBlock, etc.)
    - Número de Série (S/N explícito ou por proximidade com modelo/código numérico)
    - MAC Address
    """
    info: Dict[str, Optional[str]] = {
        "marca": None,
        "modelo": None,
        "numero_serie": None,
        "mac_address": None,
        "raw_text": raw_text
    }

    if not raw_text:
        return info

    # 1. Padrões de MAC Address (ex: AA:BB:CC:DD:EE:FF ou AA-BB-CC-DD-EE-FF)
    mac_regex = re.compile(
        r'(?:MAC(?:\s*ADDR)?[:\s]*)?([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})',
        re.IGNORECASE
    )
    mac_match = mac_regex.search(raw_text)
    if mac_match:
        raw_mac = re.sub(r'[^0-9A-Fa-f]', '', mac_match.group(1)).upper()
        if len(raw_mac) == 12:
            info["mac_address"] = ':'.join(raw_mac[i:i+2] for i in range(0, 12, 2))

    # Caso não tenha pontuação no MAC: ex "MAC: AABBCCDDEEFF"
    if not info["mac_address"]:
        mac_plain_regex = re.compile(r'MAC(?:\s*ADDR)?[:\s]*([0-9A-Fa-f]{12})\b', re.IGNORECASE)
        match_plain = mac_plain_regex.search(raw_text)
        if match_plain:
            raw_mac = match_plain.group(1).upper()
            info["mac_address"] = ':'.join(raw_mac[i:i+2] for i in range(0, 12, 2))

    mac_cleaned = info["mac_address"].replace(":", "") if info["mac_address"] else None

    # 2. Identificação de Marca
    raw_upper = raw_text.upper()
    if any(b in raw_upper for b in ["CONTROL ID", "CONTROLID", "CONTROL-ID"]) or "IDFACE" in raw_upper or "IDBLOCK" in raw_upper:
        info["marca"] = "Control iD"
    elif "INTELBRAS" in raw_upper:
        info["marca"] = "Intelbras"
    elif "HIKVISION" in raw_upper:
        info["marca"] = "Hikvision"
    elif "ZKTECO" in raw_upper or "ZK TECO" in raw_upper:
        info["marca"] = "ZKTeco"

    # 3. Identificação de Modelo
    for model_key, model_display in KNOWN_MODELS.items():
        if model_key in raw_upper:
            info["modelo"] = model_display
            break

    # Se não achou na lista de conhecidos, tenta campo "Modelo:"
    if not info["modelo"]:
        model_regex = re.compile(r'(?:MODELO|MODEL)[\s:#]+([A-Za-z0-9\-\s]{3,20})', re.IGNORECASE)
        model_match = model_regex.search(raw_text)
        if model_match:
            cand_model = model_match.group(1).splitlines()[0].strip()
            if cand_model.upper() not in STOP_WORDS:
                info["modelo"] = cand_model

    # 4. Identificação de Número de Série
    # Passo A: Prefixo explícito (SN, S/N, SERIAL, Nº, N/S, etc.)
    explicit_sn_regex = re.compile(
        r'(?:S[\/\.\\|I]?N|SERIAL(?:\s*NO|\s*NUMERO)?|N[\/\.\\|I]?S|N[º°o]\.?(?:\s*S[EÉ]RIE)?)[\s:#-]*([A-Za-z0-9\-_*|]{4,25})',
        re.IGNORECASE
    )
    for match in explicit_sn_regex.finditer(raw_text):
        cand = clean_token(match.group(1))
        if not is_blacklisted(cand, mac_cleaned):
            if any(c.isdigit() for c in cand):
                info["numero_serie"] = cand
                break

    lines = [clean_token(l) for l in raw_text.splitlines() if clean_token(l)]

    # Passo B: Heurística Control iD / Abaixo da Marca ou Modelo
    # Em produtos Control iD, o adesivo contém a marca/modelo e o número de série logo abaixo
    if not info["numero_serie"]:
        anchor_indices = []
        for idx, line in enumerate(lines):
            l_up = line.upper()
            if any(k in l_up for k in ["CONTROL", "IDFACE", "IDBLOCK", "IDBOX", "IDFLEX", "IDCLASS", "IDLOCK", "MODELO", "MODEL"]):
                anchor_indices.append(idx)
            elif info["modelo"] and info["modelo"].upper() in l_up:
                anchor_indices.append(idx)

        # Procura nas linhas imediatamente seguintes (1, 2, 3 linhas abaixo)
        for anchor_idx in anchor_indices:
            for offset in [1, 2, 3]:
                cand_idx = anchor_idx + offset
                if cand_idx < len(lines):
                    cand_line = lines[cand_idx]
                    tokens = cand_line.split()
                    for tok in tokens:
                        tok_clean = clean_token(tok)
                        if not is_blacklisted(tok_clean, mac_cleaned):
                            # Números de série Control iD tipicamente são puramente numéricos (6 a 12 dígitos, ex: 00012345)
                            if tok_clean.isdigit() and 5 <= len(tok_clean) <= 12:
                                info["numero_serie"] = tok_clean
                                break
                            # Ou alfanuméricos com pelo menos 3 dígitos
                            elif re.match(r'^[A-Za-z0-9\-_]{5,16}$', tok_clean):
                                if sum(1 for c in tok_clean if c.isdigit()) >= 3:
                                    info["numero_serie"] = tok_clean
                                    break
                    if info["numero_serie"]:
                        break
            if info["numero_serie"]:
                break

    # Passo C: Procurar números entre marcadores de código de barras (ex: *00012345*)
    if not info["numero_serie"]:
        barcode_regex = re.compile(r'[*|]\s*([A-Za-z0-9\-_]{5,16})\s*[*|]')
        for b_match in barcode_regex.finditer(raw_text):
            cand = clean_token(b_match.group(1))
            if not is_blacklisted(cand, mac_cleaned) and any(c.isdigit() for c in cand):
                info["numero_serie"] = cand
                break

    # Passo D: Fallback Geral - Procurar por sequências numéricas de 6 a 10 dígitos (típico de Control iD)
    if not info["numero_serie"]:
        for line in lines:
            for tok in line.split():
                tok_clean = clean_token(tok)
                if not is_blacklisted(tok_clean, mac_cleaned):
                    if tok_clean.isdigit() and 6 <= len(tok_clean) <= 10:
                        info["numero_serie"] = tok_clean
                        break
            if info["numero_serie"]:
                break

    # Passo E: Fallback Alfanumérico geral
    if not info["numero_serie"]:
        for line in lines:
            for tok in line.split():
                tok_clean = clean_token(tok)
                if not is_blacklisted(tok_clean, mac_cleaned):
                    if re.match(r'^[A-Za-z0-9\-_]{5,16}$', tok_clean):
                        if sum(1 for c in tok_clean if c.isdigit()) >= 2:
                            info["numero_serie"] = tok_clean
                            break
            if info["numero_serie"]:
                break

    return info
