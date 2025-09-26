from flask import Flask, request, render_template_string, redirect
import re
from urllib.parse import quote

app = Flask(__name__)

# HTML template
TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Настройка {{ app_name }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        }
        .logo { font-size: 3em; margin-bottom: 20px; }
        h1 { margin-bottom: 20px; }
        .btn {
            display: inline-block;
            padding: 15px 30px;
            background: {{ btn_color }};
            color: white;
            text-decoration: none;
            border-radius: 25px;
            font-size: 18px;
            margin: 10px;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: {{ btn_hover_color }};
            transform: translateY(-2px);
        }
        .manual-config {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            font-family: monospace;
            word-break: break-all;
            font-size: 12px;
            cursor: pointer;
        }
        .instructions {
            margin-top: 20px;
            text-align: left;
            max-width: 500px;
        }
        .step {
            margin: 10px 0;
            padding: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">{{ logo }}</div>
        <h1>Настройка {{ app_name }}</h1>
        
        {% if is_mobile %}
            <p>Нажмите кнопку ниже для автоматической настройки приложения {{ app_name }}:</p>
            <a href="{{ app_url }}" class="btn">
                📱 Открыть в {{ app_name }}
            </a>
            
            <div class="instructions">
                <h3>Инструкции:</h3>
                <div class="step">1️⃣ Нажмите кнопку "Открыть в {{ app_name }}"</div>
                <div class="step">2️⃣ Если приложение не установлено, скачайте его из App Store/Google Play</div>
                <div class="step">3️⃣ Конфигурация будет добавлена автоматически</div>
                <div class="step">4️⃣ Активируйте VPN подключение в приложении</div>
            </div>
        {% else %}
            <p>Для настройки на компьютере скопируйте ссылку ниже в приложение {{ app_name }}:</p>
        {% endif %}
        
        <div class="manual-config" onclick="copyToClipboard()">
            <strong>Ссылка подписки (нажмите для копирования):</strong><br>
            {{ subscription_url }}
        </div>
        
        <p style="margin-top: 30px;">
            <small>Если автоматическая настройка не работает, скопируйте ссылку выше и вставьте её в приложение вручную.</small>
        </p>
    </div>
    <script>
        {% if is_mobile %}
        setTimeout(function() {
            window.location.href = "{{ app_url }}";
        }, 3000);
        {% endif %}
        
        function copyToClipboard() {
            navigator.clipboard.writeText("{{ subscription_url }}").then(function() {
                alert('Ссылка скопирована в буфер обмена!');
            });
        }
    </script>
</body>
</html>
'''
IOS_V2RAYTUN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Настройка v2raytun для iOS</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        }
        .logo { font-size: 3em; margin-bottom: 20px; }
        h1 { margin-bottom: 20px; }
        .btn {
            display: inline-block;
            padding: 15px 30px;
            background: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 25px;
            font-size: 18px;
            margin: 10px;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: #45a049;
            transform: translateY(-2px);
        }
        .manual-config {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            font-family: monospace;
            word-break: break-all;
            font-size: 12px;
            cursor: pointer;
        }
        .instructions {
            margin-top: 20px;
            text-align: left;
            max-width: 500px;
        }
        .step {
            margin: 10px 0;
            padding: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🚀</div>
        <h1>Настройка v2raytun для iOS</h1>
        <p>Нажмите кнопку для открытия в приложении:</p>
        
        <a href="{{ app_url }}" class="btn" onclick="tryAlternatives()">
            📱 Открыть в v2raytun
        </a>
        
        <div class="instructions">
            <h3>Если не работает автоматически:</h3>
            <div class="step">1️⃣ Скопируйте ссылку ниже</div>
            <div class="step">2️⃣ Откройте приложение v2raytun</div>
            <div class="step">3️⃣ Нажмите "+" для добавления подписки</div>
            <div class="step">4️⃣ Вставьте скопированную ссылку</div>
        </div>
        
        <div class="manual-config" onclick="copyToClipboard()">
            <strong>Ссылка подписки (нажмите для копирования):</strong><br>
            {{ subscription_url }}
        </div>
    </div>
    
    <script>
        let attemptIndex = 0;
        const schemes = ["{{ app_url }}", {% for scheme in alt_schemes %}"{{ scheme }}"{% if not loop.last %},{% endif %}{% endfor %}];
        
        function tryAlternatives() {
            if (attemptIndex < schemes.length - 1) {
                attemptIndex++;
                setTimeout(() => {
                    window.location.href = schemes[attemptIndex];
                }, 2000);
            }
        }
        
        // Try the first scheme automatically after 2 seconds
        setTimeout(function() {
            window.location.href = "{{ app_url }}";
            tryAlternatives();
        }, 2000);
        
        function copyToClipboard() {
            navigator.clipboard.writeText("{{ subscription_url }}").then(function() {
                alert('Ссылка скопирована! Теперь откройте приложение v2raytun и добавьте подписку вручную.');
            });
        }
    </script>
</body>
</html>
'''

ANDROID_V2RAYTUN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Настройка v2raytun</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        }
        .logo { font-size: 3em; margin-bottom: 20px; }
        h1 { margin-bottom: 20px; }
        .btn {
            display: inline-block;
            padding: 15px 30px;
            background: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 25px;
            font-size: 18px;
            margin: 10px;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: #45a049;
            transform: translateY(-2px);
        }
        .manual-config {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            font-family: monospace;
            word-break: break-all;
            font-size: 12px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🚀</div>
        <h1>Настройка v2raytun</h1>
        
        <p>Попробуйте открыть приложение одним из способов:</p>
        
        <a href="{{ app_url }}" class="btn">
            📱 Открыть в v2raytun
        </a>
        
        <div class="manual-config" onclick="copyToClipboard()">
            <strong>Ссылка подписки (нажмите для копирования):</strong><br>
            {{ subscription_url }}
        </div>
        
        <p style="margin-top: 30px;">
            <small>Если автоматическая настройка не работает, скопируйте ссылку выше и вставьте её в приложение вручную.</small>
        </p>
    </div>
    <script>
        setTimeout(function() {
            window.location.href = "{{ app_url }}";
        }, 3000);
        
        function copyToClipboard() {
            navigator.clipboard.writeText("{{ subscription_url }}").then(function() {
                alert('Ссылка скопирована в буфер обмена!');
            });
        }
    </script>
</body>
</html>
'''

def detect_platform(user_agent):
    is_ios = 'iPhone' in user_agent or 'iPad' in user_agent
    is_android = 'Android' in user_agent
    return is_ios, is_android, is_ios or is_android

@app.route('/redirect-v2raytun')
def redirect_v2raytun():
    subscription_url = request.args.get('url')
    if not subscription_url:
        return "Missing URL parameter", 400
    
    user_agent = request.headers.get('User-Agent', '')
    is_ios, is_android, is_mobile = detect_platform(user_agent)
    
    if is_ios:
        # Try multiple iOS URL schemes for v2raytun
        app_url = f"v2raytun://import/{quote(subscription_url)}"
        # Alternative schemes to try
        alt_schemes = [
            f"v2raytun://add/{quote(subscription_url)}",
            f"v2raytun://subscription/{quote(subscription_url)}",
            f"v2raytun://?url={quote(subscription_url)}"
        ]
    elif is_android:
        app_url = f"v2raytun://import/{quote(subscription_url)}"
    else:
        app_url = subscription_url
    
    if is_android:
        return render_template_string(ANDROID_V2RAYTUN_TEMPLATE,
            subscription_url=subscription_url,
            app_url=app_url
        )
    
    # For iOS, create a special template with multiple attempts
    if is_ios:
        return render_template_string(IOS_V2RAYTUN_TEMPLATE,
            subscription_url=subscription_url,
            app_url=app_url,
            alt_schemes=alt_schemes
        )
    
    return render_template_string(TEMPLATE,
        app_name="v2raytun",
        logo="🚀",
        btn_color="#4CAF50",
        btn_hover_color="#45a049",
        subscription_url=subscription_url,
        app_url=app_url,
        is_mobile=is_mobile
    )

@app.route('/redirect-hiddify')
def redirect_hiddify():
    subscription_url = request.args.get('url')
    if not subscription_url:
        return "Missing URL parameter", 400
    
    user_agent = request.headers.get('User-Agent', '')
    is_ios, is_android, is_mobile = detect_platform(user_agent)
    
    if is_mobile:
        app_url = f"hiddify://install-config?url={quote(subscription_url)}"
    else:
        app_url = subscription_url
    
    return render_template_string(TEMPLATE,
        app_name="Hiddify",
        logo="🔒",
        btn_color="#FF6B35",
        btn_hover_color="#E55A2B",
        subscription_url=subscription_url,
        app_url=app_url,
        is_mobile=is_mobile
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)