module.exports = {
    apps: [
        {
            name: "face-fastapi-app",
            script: "uvicorn",
            args: ["app.main:app", "--host", "0.0.0.0", "--port", "8009"],
            interpreter: "python3"
        }
    ]
};
