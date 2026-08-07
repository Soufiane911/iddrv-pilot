FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_ENABLE_3D=false
ARG VITE_SKIP_AUTH=false
ENV VITE_ENABLE_3D=$VITE_ENABLE_3D
ENV VITE_SKIP_AUTH=$VITE_SKIP_AUTH
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
