package com.ragguard.orchestrator.controller;

import com.ragguard.orchestrator.model.dto.AuthDtos;
import com.ragguard.orchestrator.security.UserPrincipal;
import com.ragguard.orchestrator.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public ResponseEntity<AuthDtos.LoginResponse> login(@Valid @RequestBody AuthDtos.LoginRequest request) {
        AuthDtos.LoginResponse response = authService.authenticate(request);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/register")
    public ResponseEntity<AuthDtos.LoginResponse> register(@Valid @RequestBody AuthDtos.RegisterRequest request) {
        AuthDtos.LoginResponse response = authService.register(request);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/me")
    public ResponseEntity<AuthDtos.UserInfo> getCurrentUser(@AuthenticationPrincipal UserPrincipal userPrincipal) {
        return ResponseEntity.ok(userPrincipal != null
                ? AuthDtos.UserInfo.builder()
                        .id(userPrincipal.getId())
                        .username(userPrincipal.getUsername())
                        .role(userPrincipal.getRole())
                        .department(userPrincipal.getDepartment())
                        .build()
                : null);
    }

    @PostMapping("/validate")
    public ResponseEntity<AuthDtos.TokenValidationResponse> validateToken(@RequestHeader("Authorization") String authHeader) {
        String token = authHeader != null && authHeader.startsWith("Bearer ") ? authHeader.substring(7) : null;
        if (token == null) {
            return ResponseEntity.ok(AuthDtos.TokenValidationResponse.builder().valid(false).build());
        }
        return ResponseEntity.ok(authService.validateToken(token));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        // JWT is stateless, client should delete token
        return ResponseEntity.ok().build();
    }
}