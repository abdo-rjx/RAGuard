package com.ragguard.orchestrator.controller;

import com.ragguard.orchestrator.model.User;
import com.ragguard.orchestrator.model.dto.DocumentDtos;
import com.ragguard.orchestrator.security.UserPrincipal;
import com.ragguard.orchestrator.service.DocumentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<DocumentDtos.UploadResponse> uploadDocument(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @RequestParam("file") MultipartFile file,
            @RequestParam("title") String title,
            @RequestParam(value = "department", required = false) String department,
            @RequestParam(value = "classification_level", required = false, defaultValue = "INTERNAL") String classificationLevel) {

        User user = toUser(userPrincipal);

        // Default department to user's department if not provided
        if (department == null || department.isEmpty()) {
            department = user.getDepartment();
        }

        DocumentDtos.UploadResponse response = documentService.uploadDocument(
                userPrincipal.getToken(), file, title, department, classificationLevel, user);

        return ResponseEntity.ok(response);
    }

    @GetMapping
    public ResponseEntity<DocumentDtos.DocumentListResponse> listDocuments(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {

        DocumentDtos.DocumentListResponse response = documentService.listDocuments(userPrincipal.getToken(), page, size, toUser(userPrincipal));
        return ResponseEntity.ok(response);
    }

    @GetMapping("/{id}")
    public ResponseEntity<DocumentDtos.DocumentResponse> getDocument(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @PathVariable Long id) {

        DocumentDtos.DocumentResponse response = documentService.getDocument(userPrincipal.getToken(), id, toUser(userPrincipal));
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteDocument(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @PathVariable Long id) {

        documentService.deleteDocument(userPrincipal.getToken(), id, toUser(userPrincipal));
        return ResponseEntity.ok().build();
    }

    @PatchMapping("/{id}")
    public ResponseEntity<DocumentDtos.DocumentResponse> updateDocument(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @PathVariable Long id,
            @Valid @RequestBody DocumentDtos.UpdateDocumentRequest request) {

        DocumentDtos.DocumentResponse response = documentService.updateDocument(userPrincipal.getToken(), id, request, toUser(userPrincipal));
        return ResponseEntity.ok(response);
    }

    @PostMapping("/search")
    public ResponseEntity<List<DocumentDtos.SearchResult>> searchDocuments(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @Valid @RequestBody DocumentDtos.SearchRequest request) {

        List<DocumentDtos.SearchResult> results = documentService.searchDocuments(userPrincipal.getToken(), request, toUser(userPrincipal));
        return ResponseEntity.ok(results);
    }

    @PostMapping("/reindex")
    public ResponseEntity<Void> reindexDocuments(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @Valid @RequestBody DocumentDtos.ReindexRequest request) {

        documentService.reindexDocuments(userPrincipal.getToken(), request, toUser(userPrincipal));
        return ResponseEntity.ok().build();
    }

    private User toUser(UserPrincipal principal) {
        return User.builder()
                .id(principal.getId())
                .username(principal.getUsername())
                .role(principal.getRole())
                .department(principal.getDepartment())
                .build();
    }
}