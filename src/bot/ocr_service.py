import re
import io
import logging
from typing import Optional, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)

def preprocess_image(image: Image.Image) -> Image.Image:
    """Aplica escala de cinza e realce de contraste para melhor leitura de etiquetas."""
    # Converte para escala de cinza
    gray = image.convert('L')
    # Aumenta contraste
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(1.8)
    return enhanced

def extract_text_from_bytes(image_bytes: bytes) -> str:
    """Extrai texto bruto de uma imagem em bytes usando Tesseract OCR."""
    if not PYTESSERACT_AVAILABLE:
        logger.warning("Pytesseract não está instalado.")
        return ""

    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Tenta primeiro com pré-processamento
        processed = preprocess_image(image)
        text = pytesseract.image_to_string(processed, lang='por+eng', config='--psm 6')
        
        # Se resultado vier muito curto, tenta com a imagem original
        if len(text.strip()) < 5:
            text = pytesseract.image_to_string(image, lang='por+eng')
            
        return text.strip()
    except Exception as e:
        logger.error(f"Erro ao processar OCR da imagem: {e}")
        return ""

def parse_label_info(raw_text: str) -> Dict[str, Optional[str]]:
    """
    Busca padrões de MAC Address e Número de Série no texto extraído.
    """
    info: Dict[str, Optional[str]] = {
        "mac_address": None,
        "numero_serie": None,
        "raw_text": raw_text
    }

    if not raw_text:
        return info

    # 1. Padrões de MAC Address (ex: AA:BB:CC:DD:EE:FF ou AABBCCDDEEFF ou AA-BB-CC-DD-EE-FF)
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

    # 2. Padrões de Serial Number (SN, S/N, S\N, SIN, SERIAL, N/S)
    sn_regex = re.compile(
        r'(?:S[\/\.\\|I]?N|SERIAL(?:\s*NO|\s*NUMERO)?|N[\/\.\\|I]?S)[\s:#-]*([A-Za-z0-9\-_]{5,25})',
        re.IGNORECASE
    )
    sn_match = sn_regex.search(raw_text)
    if sn_match:
        info["numero_serie"] = sn_match.group(1).strip()
    else:
        # Se não tiver rótulo S/N explícito, busca blocos alfanuméricos isolados que pareçam ser SN
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        for line in lines:
            # Limpa ruídos comuns nas pontas
            cleaned_line = line.strip(" :.-_")
            if re.match(r'^[A-Za-z0-9]{6,20}$', cleaned_line) and not info["mac_address"]:
                info["numero_serie"] = cleaned_line
                break

    return info
