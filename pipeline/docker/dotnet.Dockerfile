# syntax=docker/dockerfile:1

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
ARG PROJECT_PATH
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
COPY . .
RUN dotnet restore "$PROJECT_PATH"
RUN dotnet publish "$PROJECT_PATH" -c "$BUILD_CONFIGURATION" -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
ARG ASSEMBLY_NAME
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:8080
ENV ASSEMBLY_NAME=${ASSEMBLY_NAME}
EXPOSE 8080
ENTRYPOINT ["sh", "-c", "exec dotnet ${ASSEMBLY_NAME}.dll"]
