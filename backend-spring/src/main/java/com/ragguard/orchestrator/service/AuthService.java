package com.ragguard.orchestrator.service;

import com.ragguard.orchestrator.config.JwtConfig;
import com.ragguard.orchestrator.model.User;
import com.ragguard.orchestrator.model.dto.AuthDtos;
import com.ragguard.orchestrator.repository.UserRepository;
import com.ragguard.orchestrator.security.UserPrincipal;
import io.jsonwebtoken.Jwts;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Date;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService implements UserDetailsService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtConfig jwtConfig;

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        User user = userRepository.findByUsername(username)
                .orElseThrow(() -> new UsernameNotFoundException("User not found: " + username));

        return UserPrincipal.builder()
                .id(user.getId())
                .username(user.getUsername())
                .role(user.getRole())
                .department(user.getDepartment())
                .authorities(java.util.Collections.singletonList(
                        new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_" + user.getRole().toUpperCase())
                ))
                .build();
    }

    @Transactional
    public AuthDtos.LoginResponse authenticate(AuthDtos.LoginRequest request) {
        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new BadCredentialsException("Invalid username or password"));

        if (!passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            throw new BadCredentialsException("Invalid username or password");
        }

        if (!user.isActive()) {
            throw new BadCredentialsException("Account is disabled");
        }

        String token = generateToken(user);
        return AuthDtos.LoginResponse.builder()
                .accessToken(token)
                .expiresIn(jwtConfig.getJwtExpirationMs() / 1000)
                .user(mapToUserInfo(user))
                .build();
    }

    @Transactional
    public AuthDtos.LoginResponse register(AuthDtos.RegisterRequest request) {
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new IllegalArgumentException("Username already exists");
        }

        User user = User.builder()
                .username(request.getUsername())
                .passwordHash(passwordEncoder.encode(request.getPassword()))
                .role(request.getRole().toUpperCase())
                .department(request.getDepartment())
                .active(true)
                .build();

        user = userRepository.save(user);

        String token = generateToken(user);
        return AuthDtos.LoginResponse.builder()
                .accessToken(token)
                .expiresIn(jwtConfig.getJwtExpirationMs() / 1000)
                .user(mapToUserInfo(user))
                .build();
    }

    public AuthDtos.TokenValidationResponse validateToken(String token) {
        try {
            var claims = Jwts.parser()
                    .verifyWith(jwtConfig.jwtSecretKey())
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            String userId = claims.getSubject();
            Optional<User> userOpt = userRepository.findById(Long.parseLong(userId));

            if (userOpt.isPresent() && userOpt.get().isActive()) {
                return AuthDtos.TokenValidationResponse.builder()
                        .valid(true)
                        .user(mapToUserInfo(userOpt.get()))
                        .build();
            }
        } catch (Exception e) {
            log.debug("Token validation failed: {}", e.getMessage());
        }

        return AuthDtos.TokenValidationResponse.builder()
                .valid(false)
                .build();
    }

    private String generateToken(User user) {
        Instant now = Instant.now();
        Instant expiry = now.plusMillis(jwtConfig.getJwtExpirationMs());

        return Jwts.builder()
                .subject(user.getId().toString())
                .claim("username", user.getUsername())
                .claim("role", user.getRole())
                .claim("department", user.getDepartment())
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiry))
                .signWith(jwtConfig.jwtSecretKey())
                .compact();
    }

    private AuthDtos.UserInfo mapToUserInfo(User user) {
        return AuthDtos.UserInfo.builder()
                .id(user.getId())
                .username(user.getUsername())
                .role(user.getRole())
                .department(user.getDepartment())
                .build();
    }
}