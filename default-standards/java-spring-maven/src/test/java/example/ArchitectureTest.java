package __JAVA_PACKAGE__;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import org.junit.jupiter.api.Test;

class ArchitectureTest {
  @Test
  void persistenceDoesNotDependOnWeb() {
    JavaClasses classes = new ClassFileImporter().importPackages("__JAVA_PACKAGE__");
    noClasses()
        .that()
        .resideInAPackage("..persistence..")
        .should()
        .dependOnClassesThat()
        .resideInAPackage("..web..")
        .allowEmptyShould(true)
        .check(classes);
  }
}
