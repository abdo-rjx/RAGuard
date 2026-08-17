package com.ragguard.orchestrator.config;

import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;

@Configuration
public class JwtConfig {

    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(JwtConfig.class);

    @Value("${ragguard.jwt.secret}")
    private String jwtSecret;

    @Bean
    public SecretKey jwtSecretKey() {
        if (jwtSecret == null || jwtSecret.equals("changeme-generate-a-real-secret")) {
            // Dev-only fallback: a random key means tokens are invalidated on every
            // restart. Make the operator aware instead of failing silently.
            log.warn("JWT_SECRET_KEY is missing or the insecure default. Using a random key — "
                    + "all tokens will be invalidated on the next restart. Set JWT_SECRET_KEY "
                    + "in the environment for stable, secure tokens.");
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