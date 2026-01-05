FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

# Build for production
# RUN npm run build

# Expose port 3000
EXPOSE 3000

# Start dev server for now (eases development)
CMD ["npm", "run", "dev"]
