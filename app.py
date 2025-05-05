import streamlit as st
import cv2
import numpy as np
import os
import sys
import time
import threading
import requests
from datetime import datetime

def find_free_port():
    """Encontra uma porta livre e retorna a URL do Streamlit."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
        return f"http://localhost:{port}"

def print_running_port():
    """Imprime a porta em que o Streamlit está rodando."""
    # Aguarda um momento para o Streamlit inicializar
    time.sleep(2)
    
    # Verifica se estamos rodando com o Streamlit
    if 'STREAMLIT_SERVER_PORT' in os.environ:
        port = os.environ['STREAMLIT_SERVER_PORT']
        print(f"\n\n===================================")
        print(f"🚀 Streamlit está rodando em: http://localhost:{port}")
        print(f"===================================\n")
    else:
        # Fallback - mostra uma mensagem genérica
        print("\n\n===================================")
        print("🚀 Streamlit está inicializando...")
        print("Verifique a mensagem do Streamlit para a URL.")
        print("===================================\n")

def login_to_api(api_base_url, username="openplc", password="openplc"):
    """Realiza login na API antes de enviar comandos."""
    url = f"{api_base_url}/login"
    # Criar payload para formulário (não JSON)
    payload = {
        "username": username,
        "password": password
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(
            url, 
            data=payload,  # Usando data para enviar como form-urlencoded
            headers=headers,
            timeout=3
        )
        
        if response.status_code == 200:
            # Criar sessão para manter o login
            session = requests.Session()
            session.post(
                url, 
                data=payload,  # Usando data para enviar como form-urlencoded
                headers=headers,
                timeout=3
            )
            return True, "Login realizado com sucesso", session
        else:
            return False, f"Erro no login: {response.status_code}", None
    except requests.exceptions.RequestException as e:
        return False, f"Erro ao conectar: {e}", None

def send_api_request(api_base_url, address, value):
    """Envia uma requisição para a API de controle."""
    url = f"{api_base_url}/point-write?value={value}&address={address}"
    print(f"url enviado {url}")
    try:
        # Usar a sessão autenticada se disponível
        if 'api_session' in st.session_state and st.session_state.api_session:
            response = st.session_state.api_session.get(url, timeout=3)
        else:
            response = requests.get(url, timeout=3)
            
        if response.status_code == 200:
            return True, "Comando enviado com sucesso"
        else:
            return False, f"Erro na requisição: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Erro ao enviar comando: {e}"

def main():
    st.title("Detector de Cores RGB com Webcam e Controle via API")
    st.write("Este aplicativo detecta cores e envia comandos via API HTTP.")
    
    # Configurações de conexão com a API
    st.sidebar.header("Configuração da API")
    api_ip = st.sidebar.text_input("Endereço IP do servidor", "172.172.23.5")
    api_port = st.sidebar.number_input("Porta da API", 1000, 9999, 2429)
    api_base_url = f"http://{api_ip}:{api_port}"
    
    # Estados para controle das cores e temporizadores
    if 'last_color_state' not in st.session_state:
        st.session_state.last_color_state = {
            "RED": False,
            "GREEN": False,
            "BLUE": False
        }
    if 'red_timer_active' not in st.session_state:
        st.session_state.red_timer_active = False
    if 'red_activation_time' not in st.session_state:
        st.session_state.red_activation_time = None
    
    # Status de conexão e sessão de API
    if 'api_test_status' not in st.session_state:
        st.session_state.api_test_status = None
    if 'api_session' not in st.session_state:
        st.session_state.api_session = None
    
    # Botão para testar API com autenticação
    if st.sidebar.button("Testar Conexão API"):
        # Primeiro realizar login
        success, message, session = login_to_api(api_base_url)
        if success:
            # Salvar a sessão autenticada
            st.session_state.api_session = session
            st.session_state.api_test_status = "success"
            st.sidebar.success(f"Conexão e login realizados com sucesso: {message}")
        else:
            st.session_state.api_test_status = "error"
            st.sidebar.error(f"Falha na autenticação: {message}")
    
    # Mostrar status da API
    api_status = "🟢 Conectado" if st.session_state.api_test_status == "success" else "🔴 Não testada" if st.session_state.api_test_status is None else "🔴 Falha na conexão"
    st.sidebar.markdown(f"**Status da API:** {api_status}")
    
    # Mapeamento de endereços para cada cor
    color_addresses = {
        "RED": "%QX0.3",
        "GREEN": "%QX0.6",
        "BLUE": "%QX0.4"
    }
    
    # Inicialização da webcam
    cap = cv2.VideoCapture(1)
    
    # Configurações da janela de detecção
    st.sidebar.header("Configurações da Janela")
    window_width = st.sidebar.slider("Largura da janela", 50, 500, 500)
    window_height = st.sidebar.slider("Altura da janela", 50, 500, 500)
    window_x = st.sidebar.slider("Posição X da janela", 0, 600, 250)
    window_y = st.sidebar.slider("Posição Y da janela", 0, 400, 150)
    
    # Configurações dos limites de detecção de cores
    st.sidebar.header("Configurações de Detecção")
    threshold = st.sidebar.slider("Limiar geral de detecção", 0, 255, 100)
    
    # Limiares específicos para cada cor
    st.sidebar.subheader("Limiares por Cor")
    red_threshold = st.sidebar.slider("Limiar Vermelho", 0, 255, threshold)
    green_threshold = st.sidebar.slider("Limiar Verde", 0, 255, threshold)
    blue_threshold = st.sidebar.slider("Limiar Azul", 0, 255, threshold)
    
    min_area_percent = st.sidebar.slider("Porcentagem mínima da área", 5, 95, 30)
    
    # Interface principal
    frame_placeholder = st.empty()
    result_placeholder = st.empty()
    color_values_placeholder = st.empty()
    command_status_placeholder = st.empty()
    
    stop_button = st.button("Parar")
    
    # Uso de sessão do Streamlit para evitar os avisos de ScriptRunContext
    if 'running' not in st.session_state:
        st.session_state.running = True
        # Imprimir porta no terminal (em um thread separado para não bloquear)
        threading.Thread(target=print_running_port).start()
    
    # Função para desligar o pino após delay
    def turn_off_red_after_delay():
        time.sleep(5)  # Espera 5 segundos
        success, message = send_api_request(api_base_url, color_addresses["RED"], 0)
        st.session_state.red_timer_active = False
        if not success:
            print(f"Falha ao desligar pino vermelho: {message}")
    
    while not stop_button:
        ret, frame = cap.read()
        if not ret:
            st.error("Não foi possível acessar a webcam.")
            break
        
        # Inverter horizontalmente (efeito espelho)
        frame = cv2.flip(frame, 1)
        
        # Desenhar retângulo para a área de detecção
        cv2.rectangle(frame, (window_x, window_y), 
                     (window_x + window_width, window_y + window_height), 
                     (255, 255, 255), 2)
        
        # Extrair a região de interesse (ROI)
        roi = frame[window_y:window_y+window_height, window_x:window_x+window_width]
        
        current_color = "NONE"
        
        if roi.size > 0:  # Verificar se o ROI é válido
            # Calcular valores médios de cada canal
            b_mean, g_mean, r_mean = np.mean(roi, axis=(0, 1))
            
            # Identificar cores usando limiares
            total_pixels = window_width * window_height
            min_required_pixels = total_pixels * (min_area_percent / 100)
            
            # Contar pixels acima do limiar para cada canal
            r_mask = roi[:,:,2] > red_threshold
            g_mask = roi[:,:,1] > green_threshold
            b_mask = roi[:,:,0] > blue_threshold
            
            r_count = np.sum(r_mask)
            g_count = np.sum(g_mask)
            b_count = np.sum(b_mask)
            
            # Determinar a cor predominante
            color_text = "Nenhuma cor predominante detectada"
            if r_count > min_required_pixels and r_mean > g_mean and r_mean > b_mean:
                color_text = "VERMELHO detectado!"
                color_box = (0, 0, 255)  # BGR para vermelho
                current_color = "RED"
            elif g_count > min_required_pixels and g_mean > r_mean and g_mean > b_mean:
                color_text = "VERDE detectado!"
                color_box = (0, 255, 0)  # BGR para verde
                current_color = "GREEN"
            elif b_count > min_required_pixels and b_mean > r_mean and b_mean > g_mean:
                color_text = "AZUL detectado!"
                color_box = (255, 0, 0)  # BGR para azul
                current_color = "BLUE"
            else:
                color_box = (200, 200, 200)  # Cinza
                current_color = "NONE"
            
            # Exibir resultado na imagem
            cv2.putText(frame, color_text, (20, 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, color_box, 2)
            
            # Mostrar os valores RGB
            values_text = f"R: {r_mean:.1f} (pixels: {r_count}) | G: {g_mean:.1f} (pixels: {g_count}) | B: {b_mean:.1f} (pixels: {b_count})"
            color_values_placeholder.text(values_text)
            
            # Destacar a cor detectada na interface
            result_placeholder.markdown(f"<h2 style='color:rgb{color_box[::-1]};'>{color_text}</h2>", 
                                       unsafe_allow_html=True)
            
            # Processar estados das cores e enviar comandos
            if current_color == "RED" and not st.session_state.last_color_state["RED"]:
                # Vermelho detectado - ativar e iniciar temporizador
                st.session_state.last_color_state["RED"] = True
                success, message = send_api_request(api_base_url, color_addresses["RED"], 1)
                if success:
                    command_status_placeholder.success(f"Vermelho ativado: {message}")
                    st.session_state.red_activation_time = datetime.now()
                    # Inicia thread para desligar após 5 segundos
                    if not st.session_state.red_timer_active:
                        st.session_state.red_timer_active = True
                        threading.Thread(target=turn_off_red_after_delay).start()
                else:
                    command_status_placeholder.error(f"Falha ao ativar vermelho: {message}")
            
            # Para verde e azul, aciona e desliga baseado na presença/ausência da cor
            for color_name in ["GREEN", "BLUE"]:
                is_active = current_color == color_name
                if is_active != st.session_state.last_color_state[color_name]:
                    st.session_state.last_color_state[color_name] = is_active
                    value = 1 if is_active else 0
                    success, message = send_api_request(api_base_url, color_addresses[color_name], value)
                    if success:
                        status = "ativado" if value == 1 else "desativado"
                        command_status_placeholder.success(f"{color_name} {status}: {message}")
                    else:
                        command_status_placeholder.error(f"Falha ao ativar {color_name}: {message}")
            
            # Se nada for detectado, verificar se há cores ativas para desligar
            if current_color == "NONE":
                # Para vermelho não precisamos fazer nada aqui pois já tem o timer
                for color_name in ["GREEN", "BLUE"]:
                    if st.session_state.last_color_state[color_name]:
                        st.session_state.last_color_state[color_name] = False
                        success, message = send_api_request(api_base_url, color_addresses[color_name], 0)
                        if success:
                            command_status_placeholder.info(f"{color_name} desativado: {message}")
                        else:
                            command_status_placeholder.error(f"Falha ao desativar {color_name}: {message}")
            
        # Converter para RGB (Streamlit espera RGB, não BGR usado pelo OpenCV)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Substituir use_column_width por use_container_width para evitar o aviso
        frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
        
        # Adicionar um pequeno delay para não sobrecarregar a interface
        cv2.waitKey(20)
    
    # Desligar todos os pinos ao parar
    for color_name, address in color_addresses.items():
        send_api_request(api_base_url, address, 0)
    
    # Liberar a câmera quando terminar
    cap.release()
    st.write("Câmera desativada.")

if __name__ == "__main__":
    main()
