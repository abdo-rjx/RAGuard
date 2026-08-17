package com.ragguard.orchestrator.config;

import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;

@Configuration
public class JwtConfig {

    @Value("${ragguard.jwt.secret}")
    private String jwtSecret;

    @Bean
    public SecretKey jwtSecretKey() {
        if (jwtSecret == null || jwtSecret.equals("changeme-generate-a-real-secret")) {
            // Generate a secure key for development
            return Keys.secretKeyFor(io.jsonwebtoken.SignatureAlgorithm.HS256);
        }
        return Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    @Value("${ragguard.jwt.expiration:3600000}")
    private long jwtExpirationMs;

    @Value("${ragguard.jwt.algorithm:HS256}")
    private String jwtAlgorithm;

    public long getJwtExpirationMs() {
        return jwtExpirationMs;
    }

    public String getJwtAlgorithm() {
        return jwtAlgorithm;
    }
}