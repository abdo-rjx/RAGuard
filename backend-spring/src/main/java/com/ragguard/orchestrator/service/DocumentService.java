package com.ragguard.orchestrator.service;

import com.ragguard.orchestrator.client.FastApiClient;
import com.ragguard.orchestrator.model.Document;
import com.ragguard.orchestrator.model.User;
import com.ragguard.orchestrator.model.dto.DocumentDtos;
import com.ragguard.orchestrator.repository.DocumentRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Slf4j
public class DocumentService {

    private final DocumentRepository documentRepository;
    private final FastApiClient fastApiClient;

    @Transactional
    public DocumentDtos.UploadResponse uploadDocument(String token, MultipartFile file,
                                                       String title, String department,
                                                       String classificationLevel, User user) {
        try {
            // Call FastAPI to process and index the document
            DocumentDtos.UploadResponse response = fastApiClient.uploadDocument(
                    token, title, department, classificationLevel,
                    file.getBytes(), file.getOriginalFilename()
            ).block();

            // Save document metadata locally
            if (response != null && response.getDocumentId() != null) {
                Document document = Document.builder()
                        .id(response.getDocumentId())
                        .title(title)
                        .fileType(file.getContentType())
                        .fileSize(file.getSize())
                        .ownerId(user.getId())
                        .department(department)
                        .classificationLevel(classificationLevel)
                        .status("INDEXED")
                        .build();
                documentRepository.save(document);
            }

            return response;
        } catch (IOException e) {
            log.error("Error uploading document: {}", e.getMessage());
            throw new RuntimeException("Failed to upload document", e);
        }
    }

    public DocumentDtos.DocumentListResponse listDocuments(String token, int page, int size, User user) {
        return fastApiClient.listDocuments(token, page, size).block();
    }

    public DocumentDtos.DocumentResponse getDocument(String token, Long documentId, User user) {
        // Check access permission
        Optional<Document> docOpt = documentRepository.findByIdAndOwnerId(documentId, user.getId());
        if (docOpt.isEmpty() && !"ADMIN".equals(user.getRole())) {
            // Also check department access
            docOpt = documentRepository.findById(documentId);
            if (docOpt.isPresent() && !docOpt.get().getDepartment().equals(user.getDepartment()) && !"ADMIN".equals(user.getRole())) {
                throw new SecurityException("Access denied to this document");
            }
        }

        return fastApiClient.getDocument(token, documentId).block();
    }

    @Transactional
    public void deleteDocument(String token, Long documentId, User user) {
        Optional<Document> docOpt = documentRepository.findByIdAndOwnerId(documentId, user.getId());
        if (docOpt.isEmpty() && !"ADMIN".equals(user.getRole())) {
            throw new SecurityException("Access denied to delete this document");
        }

        fastApiClient.deleteDocument(token, documentId).block();
        documentRepository.deleteById(documentId);
    }

    public DocumentDtos.DocumentResponse updateDocument(String token, Long documentId,
                                                         DocumentDtos.UpdateDocumentRequest request, User user) {
        Optional<Document> docOpt = documentRepository.findByIdAndOwnerId(documentId, user.getId());
        if (docOpt.isEmpty() && !"ADMIN".equals(user.getRole())) {
            throw new SecurityException("Access denied to update this document");
        }

        DocumentDtos.DocumentResponse response = fastApiClient.updateDocument(token, documentId, request).block();

        if (response != null) {
            Document doc = docOpt.orElseThrow();
            if (request.getTitle() != null) doc.setTitle(request.getTitle());
            if (request.getDepartment() != null) doc.setDepartment(request.getDepartment());
            if (request.getClassificationLevel() != null) doc.setClassificationLevel(request.getClassificationLevel());
            documentRepository.save(doc);
        }

        return response;
    }

    public List<DocumentDtos.SearchResult> searchDocuments(String token, DocumentDtos.SearchRequest request, User user) {
        return fastApiClient.searchDocuments(token, request).block();
    }

    @Transactional
    public void reindexDocuments(String token, DocumentDtos.ReindexRequest request, User user) {
        if (!"ADMIN".equals(user.getRole()) && !"ANALYST".equals(user.getRole())) {
            throw new SecurityException("Only admins and analysts can trigger reindexing");
        }
        fastApiClient.reindexDocuments(token, request).block();
    }
}