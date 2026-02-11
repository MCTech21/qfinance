# Issue: fix/frontend-api-baseurl-and-ec2-deploy

Tenemos el proyecto QFinance en GitHub. En EC2 servimos el frontend con nginx (puerto 8088, root /var/www/qfinance/) y el backend FastAPI corre en 127.0.0.1:8000 detrás de nginx vía proxy /api.

Problema actual (regresión):
En producción, el frontend sigue intentando pegarle a:
https://expense-tracker-app-18.preview.emergentagent.com/api/...
lo cual causa CORS/404. Ya confirmamos que ese string aparece en builds viejos (por ejemplo en build/static/js/main.*.js) y cuando el build en EC2 falla (OOM), el rsync no copia nada y nos quedamos sirviendo el JS viejo.

Objetivo:
1. El frontend debe usar API relativa por defecto (/api/...) cuando REACT_APP_BACKEND_URL esté vacío o no exista.
2. Debe ser imposible que se cuele un hardcode a emergentagent en un build sin que truene el pipeline/script.
3. El build/deploy en EC2 debe ser repetible y con protecciones (OOM/swap/NODE_OPTIONS).
