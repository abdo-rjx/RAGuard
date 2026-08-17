package com.ragguard.orchestrator.service;

import com.ragguard.orchestrator.config.JwtConfig;
import com.ragguard.orchestrator.model.User;
import com.ragguard.orchestrator.model.dto.AuthDtos;
import com.ragguard.orchestrator.repository.UserRepository;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.security.crypto.password.PasswordEncoder;

import javax.crypto.SecretKey;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Regression tests for the self-registration privilege-escalation fix:
 * a public /auth/register must never let a client request the ADMIN role.
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class AuthServiceTest {

    private static final SecretKey TEST_KEY =
            Keys.hmacShaKeyFor("0123456789abcdef0123456789abcdef".getBytes());

    @Mock
    private UserRepository userRepository;
    @Mock
    private PasswordEncoder passwordEncoder;
    @Mock
    private JwtConfig jwtConfig;

    private AuthService authService;

    @BeforeEach
    void setUp() {
        authService = new AuthService(userRepository, passwordEncoder, jwtConfig);
        when(jwtConfig.jwtSecretKey()).thenReturn(TEST_KEY);
        when(jwtConfig.getJwtExpirationMs()).thenReturn(3_600_000L);
    }

    private AuthDtos.RegisterRequest registerRequest(String role) {
        return AuthDtos.RegisterRequest.builder()
                .username("newuser")
                .password("Password123!")
                .role(role)
                .build();
    }

    @Test
    void registerRejectsAdminRole() {
        when(userRepository.existsByUsername("newuser")).thenReturn(false);

        assertThrows(IllegalArgumentException.class,
                () -> authService.register(registerRequest("ADMIN")),
                "Self-registration must never grant the ADMIN role");

        verify(userRepository, never()).save(any());
    }

    @Test
    void registerRejectsUnknownRole() {
        when(userRepository.existsByUsername("newuser")).thenReturn(false);

        assertThrows(IllegalArgumentException.class,
                () -> authService.register(registerRequest("SUPERUSER")));
    }

    @Test
    void registerAllowsUserRole() {
        when(userRepository.existsByUsername("newuser")).thenReturn(false);
        when(passwordEncoder.encode(anyString())).thenReturn("hash");
        when(userRepository.save(any(User.class))).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            u.setId(1L); // token generation needs a persisted id
            return u;
        });

        AuthDtos.LoginResponse response = authService.register(registerRequest("USER"));

        assertEquals("USER", response.getUser().getRole());
        verify(userRepository).save(argThat(u -> "USER".equals(u.getRole())));
    }

    @Test
    void registerNormalizesAnalystRole() {
        when(userRepository.existsByUsername("newuser")).thenReturn(false);
        when(passwordEncoder.encode(anyString())).thenReturn("hash");
        when(userRepository.save(any(User.class))).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            u.setId(1L); // token generation needs a persisted id
            return u;
        });

        authService.register(registerRequest("analyst")); // lowercase → normalized

        verify(userRepository).save(argThat(u -> "ANALYST".equals(u.getRole())));
    }
}
