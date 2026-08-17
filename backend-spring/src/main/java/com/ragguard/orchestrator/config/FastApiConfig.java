package com.ragguard.orchestrator.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.time.Duration;

@Configuration
public class FastApiConfig {

    @Value("${ragguard.fastapi.base-url:http://localhost:8000}")
    private String baseUrl;

    @Value("${ragguard.fastapi.timeout:30s}")
    private Duration timeout;

    @Value("${ragguard.fastapi.connect-timeout:5s}")
    private Duration connectTimeout;

    @Bean
    public WebClient fastApiWebClient() {
        ConnectionProvider provider = ConnectionProvider.builder("fastapi-pool")
                .maxConnections(50)
                .pendingAcquireMaxCount(100)
                .pendingAcquireTimeout(Duration.ofSeconds(5))
                .maxIdleTime(Duration.ofSeconds(30))
                .maxLifeTime(Duration.ofMinutes(5))
                .evictInBackground(Duration.ofSeconds(10))
                .build();

        HttpClient httpClient = HttpClient.create(provider)
                .responseTimeout(timeout)
                .option(io.netty.channel.ChannelOption.CONNECT_TIMEOUT_MILLIS, (int) connectTimeout.toMillis())
                .doOnConnected(conn -> conn.addHandlerLast(new io.netty.handler.logging.LoggingHandler("fastapi-client")));

        return WebClient.builder()
                .baseUrl(baseUrl)
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .defaultHeader("Content-Type", "application/json")
                .build();
    }
}